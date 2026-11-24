#!/usr/bin/env python3
"""M2-UX7-B experimental x86_64 TinyCC backend, STRICT HTMLK→HKEX.

Not a browser compiler: this invokes local tcc, gcc (entry assembly), ld,
readelf and objcopy. Only the canonical typed HTMLK-to-C output is accepted.
The kernel's existing GCC proof is unchanged; TCC proof is explicit opt-in.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__:
    from .build_html_user_image import assert_safe_relocations
    from .build_user_image import MAX_CODE_BYTES, pack
else:
    from build_html_user_image import assert_safe_relocations
    from build_user_image import MAX_CODE_BYTES, pack
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from compiler.htmlk import compile_html  # noqa: E402

MAX_SOURCE_BYTES=4096
RODATA_LITERAL='static const unsigned char message[] = {'
TCC_RODATA_LITERAL='static const unsigned char message[] __attribute__((section(".rodata"))) = {'
UNREACHABLE='__builtin_unreachable();'
TCC_UNREACHABLE='__asm__ volatile ("ud2");'


def adapt_generated_c(c_source: str) -> str:
    """TinyCC ABI compatibility for *canonical compiler-generated* user C.

    TCC 0.9.27 places even const static arrays into writable .data and does
    not implement GCC's __builtin_unreachable. Keep source code/read-only
    semantics with an explicit .rodata annotation and an actual UD2 trap.
    No unsafe generic source rewriting: exact known phrases only.
    """
    if not c_source.startswith('/* Generated from HTML Kernel language. x86-64 native C. */\n'):
        raise ValueError('TinyCC accepts only canonical HTMLK-generated user C')
    if '"int $0x80"' not in c_source or '#include <stdint.h>' not in c_source:
        raise ValueError('missing canonical HTMLK user ABI')
    result=c_source.replace(RODATA_LITERAL,TCC_RODATA_LITERAL)
    result=result.replace(UNREACHABLE,TCC_UNREACHABLE)
    if RODATA_LITERAL in result or UNREACHABLE in result:
        raise ValueError('unconverted canonical TCC compatibility construct')
    if 'outb' in result:
        raise ValueError('native user code must not directly access I/O ports')
    return result


def run(*arguments: str | Path) -> str:
    done=subprocess.run([str(x) for x in arguments],capture_output=True,text=True,
                        check=True,timeout=30)
    return done.stdout


def allocated_sections(readelf: str) -> list[tuple[str,int,str]]:
    """Read the full ELF section table; fail if an allocated line is malformed."""
    found=[]
    for line in readelf.splitlines():
        text=line.replace('[',' ').replace(']',' ').split()
        if len(text)<10 or not text[0].isdigit():
            continue
        # readelf -WS columns after stripping brackets:
        # [Nr] Name Type Address Off Size ES Flg Lk Inf Al
        try:
            flags=text[7]
            size=int(text[5],16)
        except (ValueError,IndexError) as error:
            raise ValueError('malformed ELF allocated section') from error
        if 'A' in flags:
            if text[2] not in ('PROGBITS','NOBITS'):
                raise ValueError('unsupported allocated ELF section type: '+text[2])
            found.append((text[1],size,flags))
    return found


def undefined_symbols(readelf_symbols: str) -> set[str]:
    """Only named, line-local UND symbols; never capture a following row."""
    undefined=set()
    for line in readelf_symbols.splitlines():
        fields=line.split()
        if len(fields)>=8 and fields[0].endswith(':') and \
                fields[0][:-1].isdigit() and fields[-2]=='UND':
            undefined.add(fields[-1])
    return undefined


def require_tcc_sections(object_table: str, linked_table: str) -> None:
    parts=allocated_sections(object_table)
    if not any(name=='.text' and length>0 and 'X' in flags
               for name,length,flags in parts):
        raise ValueError('TinyCC object must have executable .text')
    for name,length,flags in parts:
        if name=='.text' and 'X' in flags:
            continue
        if name=='.rodata' and 'X' not in flags and 'W' not in flags:
            continue
        if name in ('.data','.bss') and length==0:
            continue
        raise ValueError('unsupported allocated TinyCC section: '+name)
    linked=allocated_sections(linked_table)
    if len(linked)!=1 or linked[0][0]!='.text' or linked[0][1]<=0 or 'X' not in linked[0][2]:
        raise ValueError('HKEX final ELF must contain only .text, not writable sections: '+str(linked))


def build(source: Path, output: Path, *, tcc: str = 'tcc') -> bytes:
    if source.is_symlink() or not source.is_file() or not (0<source.stat().st_size<=MAX_SOURCE_BYTES):
        raise ValueError('TinyCC user HTML must be a regular file of 1..4096 bytes')
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise ValueError('refusing non-regular or symlink image output')
    original=source.read_text(encoding='utf-8')
    generated=adapt_generated_c(compile_html(original,target='user'))
    version=subprocess.run([tcc,'-v'],capture_output=True,text=True,
                           check=True,timeout=10)
    if 'x86_64' not in version.stdout+version.stderr:
        raise ValueError('the TinyCC binary does not generate x86_64 machine code')
    with tempfile.TemporaryDirectory(prefix='htmlk-tcc-user-') as tmp:
        folder=Path(tmp)
        c_file=folder/'canonical-user-tcc.c'
        obj=folder/'tcc-user.o'
        entry=folder/'user-entry.o'
        elf=folder/'user.elf'
        raw=folder/'user.text'
        c_file.write_text(generated,encoding='utf-8')
        # No system C headers or installed platform libraries are needed by
        # the generated code. Future WASM TCC port can use this exact header.
        run(tcc,'-std=c11','-Werror','-fno-common','-nostdinc',
            '-I',ROOT/'scripts/tcc-freestanding','-c',c_file,'-o',obj)
        head=run('readelf','-W','-h',obj)
        if 'ELF64' not in head or 'Advanced Micro Devices X86-64' not in head or 'REL (Relocatable file)' not in head:
            raise ValueError('TinyCC did not produce a relocatable x86_64 ELF object')
        assert_safe_relocations(run('readelf','-W','-r',obj))
        obj_sections=run('readelf','-W','-S',obj)
        # TCC emits a real external memset call for automatic local-array
        # zeroing. Allow exactly that one known freestanding runtime symbol;
        # fail closed on unknown host libc/compiler helper dependencies.
        symbols=run('readelf','-W','-s',obj)
        undefined=undefined_symbols(symbols)
        if undefined - {'memset'}:
            raise ValueError('TinyCC emitted unsupported external symbols: '+str(sorted(undefined)))
        run('gcc','-m64','-c','-fno-pic','-fno-pie',ROOT/'scripts/user_program_entry.S','-o',entry)
        extra=[]
        runtime_obj=folder/'tcc-memory-runtime.o'
        if 'memset' in undefined:
            run(tcc,'-std=c11','-Werror','-fno-common','-nostdinc',
                '-I',ROOT/'scripts/tcc-freestanding','-c',
                ROOT/'scripts/tcc-freestanding/runtime.c','-o',runtime_obj)
            assert_safe_relocations(run('readelf','-W','-r',runtime_obj))
            extra.append(runtime_obj)
        run('ld','-m','elf_x86_64','-nostdlib','--gc-sections','-T',
            ROOT/'scripts/user_program.ld','-o',elf,entry,obj,*extra)
        result=run('readelf','-W','-r',elf)
        if 'There are no relocations in this file.' not in result:
            raise ValueError('TinyCC final ELF retained relocations')
        linked_sections=run('readelf','-W','-S',elf)
        require_tcc_sections(obj_sections,linked_sections)
        if extra:
            require_tcc_sections(run('readelf','-W','-S',runtime_obj),linked_sections)
        run('objcopy','--only-section=.text','-O','binary',elf,raw)
        payload=raw.read_bytes()
        if not 0<len(payload)<=MAX_CODE_BYTES:
            raise ValueError('TinyCC user code exceeds single 4064-byte code page')
        image=pack(payload)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(image)
    return image


def main() -> None:
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--source',required=True,type=Path)
    arg.add_argument('--out',required=True,type=Path)
    arg.add_argument('--tcc',default='tcc',help='trusted local x86-64 TinyCC executable')
    a=arg.parse_args()
    try:
        image=build(a.source,a.out,tcc=a.tcc)
    except (OSError,UnicodeError,ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:
        arg.error(str(error))
    print('HTMLK_TCC_HKEX_IMAGE_BYTES='+str(len(image)))


if __name__=='__main__':main()
