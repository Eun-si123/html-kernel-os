# Agent commit identity and privacy

For **owner-directed AI contributions** to this public repository, use the verified public account name and no-reply email:

```sh
git config --local user.name "Eun-si123"
git config --local user.email "267835237+Eun-si123@users.noreply.github.com"
```

Add a distinguishable co-author whose display name ends in **Agent**, e.g.:

```
Co-authored-by: HTML Systems Agent <ai-assisted@users.noreply.github.com>
```

- The co-author name is freely chosen; only the suffix `Agent` is required. Do not claim a separate authenticated bot identity or fabricate a human co-author.
- For a legitimate independent human contributor, preserve **their** own public Git author identity instead of impersonating the repository owner.
- Before publishing, verify `git var GIT_AUTHOR_IDENT`, `git var GIT_COMMITTER_IDENT`, `git log -1 --format=fuller`, commit message trailers, and any CI or connector-created commit metadata.
- After publication, inspect actual GitHub commit author, committer and trailers. API-based commits and merge/squash operations may supply unexpected identities.
- Never publish private profile names, email addresses, phone numbers, identifiers, SSH host data or credentials in author/committer/trailers.
- If metadata cannot be controlled or verified, use an approved method that can, or stop before public publication. Do not automatically rewrite shared/protected branch history.
- Avoid warning loops about harmless formatting; any **actual** private-data disclosure blocks publishing until sanitized.

No automatic history rewriting, branch-protection bypass or site publication is authorized by this identity contract.

**Claude compatibility:** Preserve the owner and distinct Agent credit. An additional vendor-generated co-author of Claude or a recognized Claude model label with noreply@anthropic.com is permitted only as a co-author, not an author/committer/sign-off or proof of authenticated identity. Unexpected or private addresses remain blocked. If runtime-required metadata cannot satisfy privacy or local checks, stop before publication and report the conflict; never silently override higher-priority runtime instructions. Avoid publishing private session URLs.
