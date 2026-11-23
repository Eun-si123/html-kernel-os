/* Single flat RX page at virtual offset zero: no initialized data/BSS. */
ENTRY(htmlk_user_program_start)
SECTIONS {
  . = 0;
  .text : { KEEP(*(.text.entry)) *(.text .text.*) }
  /DISCARD/ : { *(.note.*) *(.comment) *(.eh_frame*) *(.gnu-stack) }
}
