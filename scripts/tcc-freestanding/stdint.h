/* M2-UX7-B experiment: only the exact freestanding scalar declarations used
 * by generated HTMLK x86-64 user C. No system libc or platform includes.
 * Do not broaden this to a general C standard-library implementation. */
#ifndef HTMLK_TCC_FREESTANDING_STDINT_H
#define HTMLK_TCC_FREESTANDING_STDINT_H
#ifndef __x86_64__
#error "HTMLK TinyCC bridge supports only x86_64"
#endif
typedef signed char int8_t;
typedef unsigned char uint8_t;
typedef short int16_t;
typedef unsigned short uint16_t;
typedef int int32_t;
typedef unsigned int uint32_t;
typedef long long int64_t;
typedef unsigned long long uint64_t;
#define INT32_MIN (-2147483647 - 1)
#define INT32_MAX 2147483647
#define UINT32_MAX 4294967295U
#define INT64_MIN (-9223372036854775807LL - 1LL)
#define INT64_MAX 9223372036854775807LL
#define UINT64_MAX 18446744073709551615ULL
#define INT32_C(v) v
#define UINT32_C(v) v##U
#define INT64_C(v) v##LL
#define UINT64_C(v) v##ULL
#endif
