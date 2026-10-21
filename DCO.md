# Developer Certificate of Origin (DCO)

Contributions to this project are licensed under the same terms as the
project itself (see LICENSE) and require a sign-off certifying the
Developer Certificate of Origin (https://developercertificate.org):

```
Developer Certificate of Origin
Version 1.1
...
```

Every commit in a pull request MUST carry a `Signed-off-by:` trailer:

```
Signed-off-by: Name Surname <email@example.com>
```

Add it with `git commit -s` (or `git commit -s --amend` for an existing
commit). The public CI enforces this automatically (`scripts/check_dco.sh`).

```
