import { useState, useCallback, useEffect, useMemo } from 'react'
import { useAuth } from '../contexts/AuthContext'
import type { Document } from './useDocuments'

export interface FolderRow {
  id: string
  name: string
  path: string
  parent_id: string | null
  visibility: 'public' | 'private'
  created_at?: string
  updated_at?: string
}

export interface FolderNode {
  id: string
  name: string
  path: string
  parent_id: string | null
  visibility: 'public' | 'private'
  children: FolderNode[]
}

export interface FolderContents {
  folder: FolderRow | null
  subfolders: FolderNode[]
  documents: Document[]
}

export interface BreadcrumbSegment {
  id: string | null
  name: string
}

export const ROOT_PUBLIC_ID = 'root-public'
export const ROOT_PRIVATE_ID = 'root-private'

function buildTree(folders: FolderRow[]): FolderNode[] {
  const map = new Map<string, FolderNode>()
  const roots: FolderNode[] = []
  for (const f of folders) {
    map.set(f.id, { ...f, children: [] })
  }
  for (const f of folders) {
    const node = map.get(f.id)!
    if (f.parent_id && map.has(f.parent_id)) {
      map.get(f.parent_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }
  return roots
}

export function useFolderTree() {
  const { session } = useAuth()
  const [rawFolders, setRawFolders] = useState<FolderRow[]>([])
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(
    new Set([ROOT_PUBLIC_ID, ROOT_PRIVATE_ID])
  )
  const [folderContents, setFolderContents] = useState<FolderContents | null>(null)
  const [loadingContents, setLoadingContents] = useState(false)

  const loadFolders = useCallback(async () => {
    if (!session) return
    const res = await fetch('/api/folders', {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
    if (res.ok) {
      const data: FolderRow[] = await res.json()
      setRawFolders(data)
    }
  }, [session])

  const folders = useMemo<FolderNode[]>(() => {
    const publicFolders = rawFolders.filter(f => f.visibility === 'public')
    const privateFolders = rawFolders.filter(f => f.visibility === 'private')
    const publicRoots = buildTree(publicFolders)
    const privateRoots = buildTree(privateFolders)

    const publicVirtual: FolderNode = {
      id: ROOT_PUBLIC_ID,
      name: 'BOARD GAMES',
      path: '',
      parent_id: null,
      visibility: 'public',
      children: publicRoots,
    }
    const privateVirtual: FolderNode = {
      id: ROOT_PRIVATE_ID,
      name: 'MY DOCUMENTS',
      path: '',
      parent_id: null,
      visibility: 'private',
      children: privateRoots,
    }
    return [publicVirtual, privateVirtual]
  }, [rawFolders])

  const loadContents = useCallback(
    async (folderId: string | null) => {
      if (!session) return
      if (folderId === null || folderId === ROOT_PRIVATE_ID) {
        setLoadingContents(true)
        try {
          const res = await fetch('/api/documents', {
            headers: { Authorization: `Bearer ${session.access_token}` },
          })
          const docs: Document[] = res.ok ? await res.json() : []
          // Root-level documents only (no folder assigned)
          const rootDocs = docs.filter(d => !(d as unknown as { folder_id?: string }).folder_id)
          // Private root subfolders = top-level private folders
          const privateRoots = rawFolders
            .filter(f => f.visibility === 'private' && !f.parent_id)
            .map(f => ({ ...f, children: [] }))
          setFolderContents({
            folder: null,
            subfolders: privateRoots,
            documents: rootDocs,
          })
        } finally {
          setLoadingContents(false)
        }
        return
      }
      if (folderId === ROOT_PUBLIC_ID) {
        // Show top-level public folders, no documents
        const publicRoots = rawFolders
          .filter(f => f.visibility === 'public' && !f.parent_id)
          .map(f => ({ ...f, children: [] }))
        setFolderContents({
          folder: null,
          subfolders: publicRoots,
          documents: [],
        })
        return
      }
      setLoadingContents(true)
      try {
        const res = await fetch(`/api/folders/${folderId}/contents`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        })
        if (res.ok) {
          const data = await res.json()
          setFolderContents({
            folder: data.folder,
            subfolders: (data.subfolders || []).map((f: FolderRow) => ({
              ...f,
              children: [],
            })),
            documents: data.documents || [],
          })
        } else {
          setFolderContents({ folder: null, subfolders: [], documents: [] })
        }
      } finally {
        setLoadingContents(false)
      }
    },
    [session, rawFolders]
  )

  const selectFolder = useCallback(
    (id: string | null) => {
      setSelectedFolderId(id)
      if (id !== null) {
        loadContents(id)
      } else {
        setFolderContents(null)
      }
    },
    [loadContents]
  )

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const refreshTree = useCallback(() => {
    loadFolders()
    if (selectedFolderId !== null) {
      loadContents(selectedFolderId)
    }
  }, [loadFolders, loadContents, selectedFolderId])

  const breadcrumbs = useMemo<BreadcrumbSegment[]>(() => {
    if (selectedFolderId === null) return []
    if (selectedFolderId === ROOT_PUBLIC_ID) {
      return [{ id: ROOT_PUBLIC_ID, name: 'Board Games' }]
    }
    if (selectedFolderId === ROOT_PRIVATE_ID) {
      return [{ id: ROOT_PRIVATE_ID, name: 'My Documents' }]
    }
    // Walk parent chain
    const byId = new Map(rawFolders.map(f => [f.id, f] as const))
    const chain: FolderRow[] = []
    let cur = byId.get(selectedFolderId)
    while (cur) {
      chain.unshift(cur)
      cur = cur.parent_id ? byId.get(cur.parent_id) : undefined
    }
    const rootName =
      chain[0]?.visibility === 'public' ? 'Board Games' : 'My Documents'
    const rootId = chain[0]?.visibility === 'public' ? ROOT_PUBLIC_ID : ROOT_PRIVATE_ID
    const segments: BreadcrumbSegment[] = [{ id: rootId, name: rootName }]
    for (const f of chain) {
      segments.push({ id: f.id, name: f.name })
    }
    return segments
  }, [selectedFolderId, rawFolders])

  useEffect(() => {
    loadFolders()
  }, [loadFolders])

  return {
    folders,
    rawFolders,
    selectedFolderId,
    expandedIds,
    folderContents,
    loadingContents,
    selectFolder,
    toggleExpand,
    refreshTree,
    breadcrumbs,
  }
}
