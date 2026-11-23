/* Single flat RX page at virtual offset zero: no initialized data/BSS. */
ENTRY(htmlk_user_program_start)
SECTIONS {
  . = 0;
  /* Only literal read-only data may share the single user RO code page. */
  .text : { KEEP(*(.text.entry)) *(.text .text.*) *(.rodata .rodata.*) }
  /DISCARD/ : { *(.note.*) *(.comment) *(.eh_frame*) *(.gnu-stack) }
}
