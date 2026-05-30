# Recommended branch-protection settings

These settings are GitHub repository configuration, not files. Apply
them via **Settings → Branches → Add rule** on
<https://github.com/KoreaHealthDataPlatform/khdp-api>.

## `main` branch rule

- ✅ **Require a pull request before merging**
  - Require approvals: **1**
  - Dismiss stale pull request approvals when new commits are pushed
  - Require review from Code Owners (uses [`.github/CODEOWNERS`](./CODEOWNERS))
- ✅ **Require status checks to pass before merging**
  - Require branches to be up to date before merging
  - Required checks: `test (ubuntu-latest, 3.10)`, `test (ubuntu-latest, 3.11)`,
    `test (ubuntu-latest, 3.12)`, `test (macos-latest, 3.12)`,
    `test (windows-latest, 3.12)` (from [`ci.yml`](./workflows/ci.yml))
- ✅ **Require conversation resolution before merging**
- ✅ **Require signed commits** *(recommended)*
- ✅ **Require linear history**
- ✅ **Restrict who can push to matching branches**
  - Limit to the `KoreaHealthDataPlatform/maintainers` team.
- ✅ **Do not allow bypassing the above settings**
- ❌ **Allow force pushes** (off)
- ❌ **Allow deletions** (off)

## Apply via the GitHub CLI

If you have admin scope and `gh` 2.40+:

```bash
gh api -X PUT repos/KoreaHealthDataPlatform/khdp-api/branches/main/protection \
  -F required_status_checks.strict=true \
  -F required_status_checks.contexts[]='test (ubuntu-latest, 3.10)' \
  -F required_status_checks.contexts[]='test (ubuntu-latest, 3.11)' \
  -F required_status_checks.contexts[]='test (ubuntu-latest, 3.12)' \
  -F required_status_checks.contexts[]='test (macos-latest, 3.12)' \
  -F required_status_checks.contexts[]='test (windows-latest, 3.12)' \
  -F enforce_admins=false \
  -F required_pull_request_reviews.required_approving_review_count=1 \
  -F required_pull_request_reviews.require_code_owner_reviews=true \
  -F required_pull_request_reviews.dismiss_stale_reviews=true \
  -F required_linear_history=true \
  -F allow_force_pushes=false \
  -F allow_deletions=false \
  -F restrictions=null
```

> Replace `null` for `restrictions` with the team JSON if you want to
> enforce a push allowlist. Read the rest of the
> [Branches API docs](https://docs.github.com/en/rest/branches/branch-protection)
> for full options.
