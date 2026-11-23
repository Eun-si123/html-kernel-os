#include "romfs.h"

static int path_compare(const char *left, const char *right) {
    for (size_t i = 0; i <= HTMLK_ROMFS_MAX_PATH; ++i) {
        const unsigned char a = (unsigned char)left[i];
        const unsigned char b = (unsigned char)right[i];
        if (a != b) return a < b ? -1 : 1;
        if (a == 0) return 0;
    }
    return 0; /* Only called after both paths have been validated. */
}

bool htmlk_romfs_path_valid(const char *path) {
    if (path == 0 || path[0] != '/') return false;
    size_t segment_start = 1;
    for (size_t i = 1; i <= HTMLK_ROMFS_MAX_PATH; ++i) {
        const unsigned char c = (unsigned char)path[i];
        if (c == '/' || c == 0) {
            const size_t length = i - segment_start;
            if (length == 0 || (length == 1 && path[segment_start] == '.') ||
                (length == 2 && path[segment_start] == '.' &&
                 path[segment_start + 1] == '.')) return false;
            if (c == 0) return true;
            segment_start = i + 1;
        } else if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                     (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.')) {
            return false;
        }
    }
    return false;
}

bool htmlk_romfs_validate(const struct htmlk_romfs_volume *volume) {
    if (volume == 0 || volume->files == 0 || volume->count == 0 ||
        volume->count > HTMLK_ROMFS_MAX_FILES) return false;
    size_t sum = 0;
    for (size_t i = 0; i < volume->count; ++i) {
        const struct htmlk_romfs_file *file = &volume->files[i];
        if (!htmlk_romfs_path_valid(file->path) ||
            file->length > HTMLK_ROMFS_MAX_FILE_BYTES ||
            (file->length != 0 && file->data == 0) ||
            file->length > HTMLK_ROMFS_MAX_BYTES - sum) return false;
        sum += file->length;
        if (i != 0 && path_compare(volume->files[i - 1].path, file->path) >= 0)
            return false;
    }
    return true;
}

bool htmlk_romfs_read(const struct htmlk_romfs_volume *volume,
                      const char *path, size_t offset,
                      uint8_t *destination, size_t capacity, size_t *read_bytes) {
    if (read_bytes == 0) return false;
    *read_bytes = 0;
    if (!htmlk_romfs_path_valid(path) || !htmlk_romfs_validate(volume) ||
        (capacity != 0 && destination == 0)) return false;
    size_t lo = 0, hi = volume->count;
    while (lo < hi) {
        const size_t mid = lo + (hi - lo) / 2;
        const int cmp = path_compare(volume->files[mid].path, path);
        if (cmp < 0) lo = mid + 1;
        else hi = mid;
    }
    if (lo == volume->count || path_compare(volume->files[lo].path, path) != 0)
        return false;
    const struct htmlk_romfs_file *file = &volume->files[lo];
    if (offset >= file->length) return true; /* EOF, even for SIZE_MAX. */
    const size_t remaining = file->length - offset;
    const size_t amount = remaining < capacity ? remaining : capacity;
    for (size_t i = 0; i < amount; ++i) destination[i] = file->data[offset + i];
    *read_bytes = amount;
    return true;
}
