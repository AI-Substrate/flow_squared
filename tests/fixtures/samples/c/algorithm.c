/**
 * @file algorithm.c
 * @brief Common algorithm implementations for sorting and searching.
 *
 * Provides efficient implementations of fundamental algorithms
 * with generic comparator support via function pointers.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

/**
 * @brief Comparator function type for generic comparisons.
 * @param a Pointer to first element.
 * @param b Pointer to second element.
 * @return Negative if a < b, zero if equal, positive if a > b.
 */
typedef int (*Comparator)(const void* a, const void* b);

/**
 * @brief Result structure for search operations.
 */
typedef struct {
    bool found;        /**< Whether the element was found */
    size_t index;      /**< Index of the element if found */
    size_t comparisons; /**< Number of comparisons made */
} SearchResult;

/**
 * @brief Statistics for sort operations.
 */
typedef struct {
    size_t comparisons; /**< Number of comparisons made */
    size_t swaps;       /**< Number of swaps performed */
} SortStats;

/**
 * @brief Swap two elements in memory.
 * @param a Pointer to first element.
 * @param b Pointer to second element.
 * @param size Size of each element in bytes.
 */
static void swap(void* a, void* b, size_t size) {
    unsigned char* pa = (unsigned char*)a;
    unsigned char* pb = (unsigned char*)b;

    for (size_t i = 0; i < size; i++) {
        unsigned char temp = pa[i];
        pa[i] = pb[i];
        pb[i] = temp;
    }
}

/**
 * @brief Binary search in a sorted array.
 *
 * Performs binary search with O(log n) time complexity.
 * Array must be sorted in ascending order according to comparator.
 *
 * @param arr Pointer to the sorted array.
 * @param size Number of elements in the array.
 * @param elem_size Size of each element in bytes.
 * @param key Pointer to the key to search for.
 * @param cmp Comparator function.
 * @return SearchResult with found status and index.
 */
SearchResult binary_search(
    const void* arr,
    size_t size,
    size_t elem_size,
    const void* key,
    Comparator cmp
) {
    SearchResult result = { false, 0, 0 };

    if (size == 0 || arr == NULL || key == NULL || cmp == NULL) {
        return result;
    }

    size_t left = 0;
    size_t right = size - 1;

    while (left <= right) {
        size_t mid = left + (right - left) / 2;
        const void* mid_elem = (const char*)arr + mid * elem_size;

        result.comparisons++;
        int comparison = cmp(mid_elem, key);

        if (comparison == 0) {
            result.found = true;
            result.index = mid;
            return result;
        } else if (comparison < 0) {
            left = mid + 1;
        } else {
            if (mid == 0) break;
            right = mid - 1;
        }
    }

    return result;
}

/**
 * @brief Quicksort implementation with median-of-three pivot.
 *
 * In-place sorting with average O(n log n) time complexity.
 * Uses median-of-three pivot selection for better performance.
 *
 * @param arr Pointer to the array to sort.
 * @param size Number of elements.
 * @param elem_size Size of each element in bytes.
 * @param cmp Comparator function.
 * @return SortStats with operation counts.
 */
SortStats quicksort(
    void* arr,
    size_t size,
    size_t elem_size,
    Comparator cmp
) {
    SortStats stats = { 0, 0 };

    if (size <= 1 || arr == NULL || cmp == NULL) {
        return stats;
    }

    quicksort_internal(arr, 0, size - 1, elem_size, cmp, &stats);
    return stats;
}

/**
 * @brief Internal recursive quicksort implementation.
 */
static void quicksort_internal(
    void* arr,
    size_t low,
    size_t high,
    size_t elem_size,
    Comparator cmp,
    SortStats* stats
) {
    if (low >= high) return;

    // Median-of-three pivot selection
    size_t mid = low + (high - low) / 2;
    void* a = (char*)arr + low * elem_size;
    void* b = (char*)arr + mid * elem_size;
    void* c = (char*)arr + high * elem_size;

    stats->comparisons += 3;
    if (cmp(a, b) > 0) { swap(a, b, elem_size); stats->swaps++; }
    if (cmp(b, c) > 0) { swap(b, c, elem_size); stats->swaps++; }
    if (cmp(a, b) > 0) { swap(a, b, elem_size); stats->swaps++; }

    // Partition
    void* pivot = (char*)arr + mid * elem_size;
    size_t i = low;
    size_t j = high;

    while (i <= j) {
        while (cmp((char*)arr + i * elem_size, pivot) < 0) {
            stats->comparisons++;
            i++;
        }
        while (cmp((char*)arr + j * elem_size, pivot) > 0) {
            stats->comparisons++;
            j--;
        }

        if (i <= j) {
            swap((char*)arr + i * elem_size, (char*)arr + j * elem_size, elem_size);
            stats->swaps++;
            i++;
            if (j > 0) j--;
        }
    }

    // Recurse
    if (low < j) quicksort_internal(arr, low, j, elem_size, cmp, stats);
    if (i < high) quicksort_internal(arr, i, high, elem_size, cmp, stats);
}

/**
 * @brief Merge sort implementation.
 *
 * Stable sorting with guaranteed O(n log n) time complexity.
 * Requires O(n) additional memory.
 *
 * @param arr Pointer to the array to sort.
 * @param size Number of elements.
 * @param elem_size Size of each element in bytes.
 * @param cmp Comparator function.
 * @return SortStats with operation counts.
 */
SortStats merge_sort(
    void* arr,
    size_t size,
    size_t elem_size,
    Comparator cmp
) {
    SortStats stats = { 0, 0 };

    if (size <= 1 || arr == NULL || cmp == NULL) {
        return stats;
    }

    void* temp = malloc(size * elem_size);
    if (temp == NULL) {
        return stats;
    }

    merge_sort_internal(arr, temp, 0, size - 1, elem_size, cmp, &stats);
    free(temp);
    return stats;
}

/**
 * @brief Internal merge sort with auxiliary buffer.
 */
static void merge_sort_internal(
    void* arr,
    void* temp,
    size_t left,
    size_t right,
    size_t elem_size,
    Comparator cmp,
    SortStats* stats
) {
    if (left >= right) return;

    size_t mid = left + (right - left) / 2;

    merge_sort_internal(arr, temp, left, mid, elem_size, cmp, stats);
    merge_sort_internal(arr, temp, mid + 1, right, elem_size, cmp, stats);

    // Merge
    size_t i = left, j = mid + 1, k = left;

    while (i <= mid && j <= right) {
        stats->comparisons++;
        if (cmp((char*)arr + i * elem_size, (char*)arr + j * elem_size) <= 0) {
            memcpy((char*)temp + k * elem_size, (char*)arr + i * elem_size, elem_size);
            i++;
        } else {
            memcpy((char*)temp + k * elem_size, (char*)arr + j * elem_size, elem_size);
            j++;
        }
        k++;
    }

    while (i <= mid) {
        memcpy((char*)temp + k * elem_size, (char*)arr + i * elem_size, elem_size);
        i++; k++;
    }

    while (j <= right) {
        memcpy((char*)temp + k * elem_size, (char*)arr + j * elem_size, elem_size);
        j++; k++;
    }

    memcpy((char*)arr + left * elem_size, (char*)temp + left * elem_size,
           (right - left + 1) * elem_size);
    stats->swaps += right - left + 1;
}

/**
 * @brief Integer comparator for ascending order.
 */
int compare_int_asc(const void* a, const void* b) {
    int ia = *(const int*)a;
    int ib = *(const int*)b;
    return (ia > ib) - (ia < ib);
}

/**
 * @brief Integer comparator for descending order.
 */
int compare_int_desc(const void* a, const void* b) {
    return -compare_int_asc(a, b);
}
