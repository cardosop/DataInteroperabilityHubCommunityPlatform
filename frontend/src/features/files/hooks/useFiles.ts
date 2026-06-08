/**
 * Files React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { fileService } from '../services/fileService';

export function useFiles(filters: {
  page?: number;
  page_size?: number;
  asset_id?: string;
  dataset_id?: string;
  search?: string;
  ordering?: string;
} = {}, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['files', 'list', filters],
    queryFn: () => fileService.list(filters),
    enabled: options?.enabled !== false,
  });
}

export function useFile(id: string | null) {
  return useQuery({
    queryKey: ['files', 'detail', id],
    queryFn: () => fileService.getById(id!),
    enabled: !!id,
  });
}

export function useUploadFile() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({
      file,
      options,
    }: {
      file: Blob;
      options?: {
        name?: string;
        onProgress?: (progress: number) => void;
      };
    }) => fileService.uploadFile(file, options),
    successMessage: 'File uploaded',
    errorMessage: 'Failed to upload file',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}

export function useDeleteFile() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => fileService.delete(id),
    successMessage: 'File deleted',
    errorMessage: 'Failed to delete file',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}

export function useRenameFile() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      fileService.rename(id, name),
    successMessage: 'File renamed',
    errorMessage: 'Failed to rename file',
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['files', 'detail', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}

export function useFileStorageQuota() {
  return useQuery({
    queryKey: ['files', 'storage-quota'],
    queryFn: () => fileService.getStorageQuota(),
  });
}
