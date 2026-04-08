"""Tests for folder_id and visibility propagation in upload endpoint.

Validates that the document INSERT dict in documents.py includes
folder_id and visibility fields, and that the upload_document
function signature accepts folder_id as an optional Form parameter.
"""
import inspect
import ast


def test_upload_document_signature_has_folder_id():
    """upload_document must accept folder_id parameter."""
    from routers.documents import upload_document

    sig = inspect.signature(upload_document)
    assert "folder_id" in sig.parameters, "folder_id not in upload_document signature"


def test_upload_document_folder_id_is_optional():
    """folder_id parameter must default to None."""
    from routers.documents import upload_document

    sig = inspect.signature(upload_document)
    param = sig.parameters["folder_id"]
    assert param.default is not inspect.Parameter.empty, "folder_id must have a default value"


def test_document_insert_contains_folder_id():
    """Document INSERT dict in documents.py must contain 'folder_id' key."""
    import routers.documents as mod

    source = inspect.getsource(mod.upload_document)
    tree = ast.parse(source)

    # Look for dict literal containing "folder_id" key
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "folder_id":
                    found = True
                    break
    assert found, "Document INSERT dict does not contain 'folder_id' key"


def test_document_insert_contains_visibility_private():
    """Document INSERT dict in documents.py must contain 'visibility': 'private'."""
    import routers.documents as mod

    source = inspect.getsource(mod.upload_document)
    tree = ast.parse(source)

    found_key = False
    found_value = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "visibility":
                    found_key = True
                    if isinstance(value, ast.Constant) and value.value == "private":
                        found_value = True
    assert found_key, "Document INSERT dict does not contain 'visibility' key"
    assert found_value, "Document INSERT 'visibility' value is not 'private'"
