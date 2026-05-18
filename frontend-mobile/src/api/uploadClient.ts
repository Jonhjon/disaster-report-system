// 照片上傳：對應後端 /api/uploads/photo
import axios from 'axios';
import { apiUrl } from '../config/env';
import type { AttachmentOut } from '../types';

export const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
export const MAX_PHOTOS_PER_REPORT = 3;

export interface LocalPhoto {
  uri: string;
  fileName?: string;
  type?: string;
  fileSize?: number;
}

export async function uploadPhoto(photo: LocalPhoto): Promise<AttachmentOut> {
  if (photo.type && !ALLOWED_PHOTO_TYPES.includes(photo.type as (typeof ALLOWED_PHOTO_TYPES)[number])) {
    throw new Error(`僅支援 JPEG / PNG / WebP（收到 ${photo.type}）`);
  }
  if (photo.fileSize && photo.fileSize > MAX_PHOTO_BYTES) {
    throw new Error(`檔案大小超過 ${Math.round(MAX_PHOTO_BYTES / 1024 / 1024)} MB`);
  }

  const form = new FormData();
  form.append('file', {
    uri: photo.uri,
    name: photo.fileName ?? 'photo.jpg',
    type: photo.type ?? 'image/jpeg',
  } as unknown as Blob);

  const response = await axios.post<AttachmentOut>(apiUrl('/uploads/photo'), form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  });
  return response.data;
}
