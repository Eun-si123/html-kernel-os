/* M2-UX7-B1: minimal stack-array clearing for native TinyCC-only HTMLK.
 * TinyCC may synthesize a call to memset for automatic array zero-init.
 * This code has no libc, heap, system calls or browser runtime dependencies.
 * Only local 64-bit SysV calling convention is accepted by the strict builder.
 */
#include <stdint.h>
void *memset(void *destination, int byte, unsigned long count) {
    unsigned char *cursor=(unsigned char *)destination;
    const unsigned char fill=(unsigned char)byte;
    for (unsigned long i=0; i<count; ++i) {
        cursor[i]=fill;
    }
    return destination;
}
