-- Enable the ltree extension for materialized path hierarchical queries.
-- Used by the folders table for efficient tree traversal (ancestor/descendant lookups).
CREATE EXTENSION IF NOT EXISTS ltree;
