/**
 * @file vector_add.cu
 * @brief CUDA vector addition kernel and host launcher.
 *
 * Demonstrates basic GPU parallel computation with
 * thread indexing and block/grid configuration.
 */

/**
 * @brief Add two vectors element-wise on the GPU.
 *
 * Each thread computes one element: c[i] = a[i] + b[i].
 * Thread index is computed from block and thread IDs.
 *
 * @param a First input vector (device memory)
 * @param b Second input vector (device memory)
 * @param c Output vector (device memory)
 * @param n Number of elements
 */
__global__ void vectorAdd(float *a, float *b, float *c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        c[i] = a[i] + b[i];
    }
}

// Launch the vector addition kernel from host code.
// Calculates grid dimensions using 256 threads per block.
__host__ void launchKernel(float *a, float *b, float *c, int n) {
    int blockSize = 256;
    int numBlocks = (n + blockSize - 1) / blockSize;
    vectorAdd<<<numBlocks, blockSize>>>(a, b, c, n);
}
