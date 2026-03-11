/**
 * Files React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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

  return useMutation({
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}

export function useDeleteFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => fileService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}
