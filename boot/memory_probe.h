#ifndef HTMLK_MEMORY_PROBE_H
#define HTMLK_MEMORY_PROBE_H

struct limine_memmap_response;
struct limine_hhdm_response;

/* Only built for the explicit M3 test image, before kernel_main().
 * Reads the bootloader map, touches usable physical pages via HHDM and checks
 * exact exhaustion; no page-table edits or dynamic pointers in HTML source.
 */
void htmlk_memory_probe(const struct limine_memmap_response *memory_map,
                        const struct limine_hhdm_response *hhdm);

#endif
