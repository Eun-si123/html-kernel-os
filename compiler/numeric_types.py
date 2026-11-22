"""Native integer widths and overflow-safe signed helper emission.

The runtime is x86-64 C11. No signed overflow is performed in generated C:
arithmetic happens through unsigned bit patterns, then maps back into a
signed range with a fully defined conversion (including INT_MIN).
"""
INTEGER_TYPES = ("u32", "u64", "i32", "i64")
INTEGER_TYPE_SET = frozenset(INTEGER_TYPES)
UNSIGNED_TYPES = frozenset(("u32", "u64"))
SIGNED_TYPES = frozenset(("i32", "i64"))


def width(name: str) -> int:
    return 32 if name.endswith("32") else 64


def c_type(name: str) -> str:
    return ("int" if name.startswith("i") else "uint") + str(width(name)) + "_t"


def literal_macro(name: str) -> str:
    return ("INT" if name.startswith("i") else "UINT") + str(width(name)) + "_C"


def c_helpers() -> list[str]:
    result = [
        # An unsigned-to-signed narrowing cast with an out-of-range value is
        # implementation-defined in C11. Use a range-safe conversion instead.
        "static inline int32_t htmlk_from_bits_i32(uint32_t x) {",
        "  if (x <= INT32_MAX) return (int32_t)x;",
        "  return -INT32_C(1) - (int32_t)(UINT32_MAX - x);",
        "}",
        "static inline int64_t htmlk_from_bits_i64(uint64_t x) {",
        "  if (x <= INT64_MAX) return (int64_t)x;",
        "  return -INT64_C(1) - (int64_t)(UINT64_MAX - x);",
        "}",
    ]
    for kind in ("i32", "i64"):
        size = width(kind)
        result.extend([
            f"static inline {c_type(kind)} htmlk_add_{kind}({c_type(kind)} a, {c_type(kind)} b) {{",
            f"  return htmlk_from_bits_{kind}((uint{size}_t)a + (uint{size}_t)b);",
            "}",
            f"static inline {c_type(kind)} htmlk_sub_{kind}({c_type(kind)} a, {c_type(kind)} b) {{",
            f"  return htmlk_from_bits_{kind}((uint{size}_t)a - (uint{size}_t)b);",
            "}",
            f"static inline {c_type(kind)} htmlk_mul_{kind}({c_type(kind)} a, {c_type(kind)} b) {{",
            f"  return htmlk_from_bits_{kind}((uint{size}_t)a * (uint{size}_t)b);",
            "}",
            f"static inline {c_type(kind)} htmlk_neg_{kind}({c_type(kind)} a) {{",
            f"  return htmlk_from_bits_{kind}((uint{size}_t)0 - (uint{size}_t)a);",
            "}",
        ])
    for kind in ("u32", "u64"):
        size = width(kind)
        t = c_type(kind)
        result.extend([
            f"static inline {t} htmlk_shl_{kind}({t} a, {t} shift) {{",
            f"  return shift >= {size} ? ({t})0 : ({t})(a << shift);",
            "}",
            f"static inline {t} htmlk_shr_{kind}({t} a, {t} shift) {{",
            f"  return shift >= {size} ? ({t})0 : ({t})(a >> shift);",
            "}",
        ])
    return result
