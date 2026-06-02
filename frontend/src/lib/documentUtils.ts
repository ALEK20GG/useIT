export type DocumentLike = {
  title?: string;
  content?: string;
  filename?: string;
  metadata?: Record<string, unknown>;
};

export type PreviewMode = 'embed' | 'text' | 'none';

export function getFileId(doc: DocumentLike): string | undefined {
  const id = doc.metadata?.file_id;
  return typeof id === 'string' ? id : undefined;
}

export function getOriginalFilename(doc: DocumentLike): string {
  const fromMeta = doc.metadata?.original_filename;
  if (typeof fromMeta === 'string' && fromMeta) return fromMeta;
  return doc.filename || doc.title || 'documento';
}

export function getDownloadUrl(backendUrl: string, doc: DocumentLike): string | null {
  const fileId = getFileId(doc);
  return fileId ? `${backendUrl}/files/${fileId}/download` : null;
}

export function getPreviewUrl(backendUrl: string, doc: DocumentLike): string | null {
  const fileId = getFileId(doc);
  return fileId ? `${backendUrl}/files/${fileId}/preview` : null;
}

export function getPreviewMode(doc: DocumentLike): PreviewMode {
  const ct = String(doc.metadata?.content_type ?? '').toLowerCase();
  const fn = getOriginalFilename(doc).toLowerCase();
  if (ct.includes('pdf') || fn.endsWith('.pdf')) return 'embed';
  if (ct.includes('plain') || ct.includes('text') || fn.endsWith('.txt')) return 'text';
  return 'none';
}

export function fileTypeBadge(doc: DocumentLike): string {
  const ct = String(doc.metadata?.content_type ?? '').toLowerCase();
  if (ct.includes('pdf')) return 'PDF';
  if (ct.includes('word') || ct.includes('docx')) return 'DOCX';
  if (ct.includes('plain') || ct.includes('text')) return 'TXT';
  if (ct.includes('msword')) return 'DOC';
  const ext = getOriginalFilename(doc).split('.').pop()?.toUpperCase();
  if (ext && ['PDF', 'DOCX', 'DOC', 'TXT'].includes(ext)) return ext;
  return '';
}
