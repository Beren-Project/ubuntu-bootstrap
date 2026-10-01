# Installation authorities and reviewed pins

Reviewed 2026-10-01. Policies and immutable artifact inputs are centralized in
`config/bootstrap.toml`; this document records why those methods were selected.

| Component | Official guidance | Implementation |
| --- | --- | --- |
| Rust | https://rust-lang.org/tools/install/ and official rustup installer help | rustup stable/minimal, `--no-modify-path` |
| Cargo binaries | https://github.com/cargo-bins/cargo-binstall | Official release archive; manifest crates through binstall with explicit locked source fallback |
| uv | https://docs.astral.sh/uv/reference/installer/ | Official installer; `UV_NO_MODIFY_PATH=1` |
| Python | https://docs.astral.sh/uv/concepts/python-versions/ | Stable managed CPython via uv, user-local default launchers |
| Node | https://github.com/Schniz/fnm/blob/master/docs/commands.md | fnm latest LTS and managed default |
| Julia | https://docs.julialang.org/en/v1/manual/installation/ | Juliaup release, `--add-to-path=no`, no scheduled self-updates |
| Neovim | https://github.com/neovim/neovim/blob/master/INSTALL.md | Named official stable archive, GitHub release SHA-256, `/opt` installation |
| OpenModelica | https://openmodelica.org/download/download-linux/ | Official signed resolute/stable repository; `--no-install-recommends omc` |
| ngspice | https://ngspice.sourceforge.io/download.html and release `INSTALL` | Manual out-of-tree release build, normal-user staging, system publication |

Dotfiles commit `f7c3eb9ce433a1a8e285afdcda06c1da56c018fd` was inspected against
its selective restore implementation and bootstrap contract. The selected paths
are Zsh, Git, tmux and Starship only. Git identity remains personal state even
though upstream setup notes suggest creating it before restore; a missing
`.gitconfig.local` is supported and bootstrap reports that account action.

The ngspice 47 artifact was fetched from the official release distribution and
its SHA-256 matched SourceForge's published
`894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f`.
The release INSTALL recommends `../configure --with-x`, make and install;
bootstrap adds CIDER, preserves default XSPICE/OpenMP/OSDI, supplies FFTW and
sound-file dependencies, and never runs the build as root. It uses DESTDIR
staging instead of executing upstream make/install with sudo.

The official OpenModelica key contains reviewed primary fingerprints
`D229AF1CE5AED74E5F59DF303A59B53664970947` and
`5DE86CC050F6623BBA7995B864CE41328E03B30A`. Signed Release metadata and APT
package verification are both checked. A future upstream key change requires
reviewing this trust input, rather than accepting a newly downloaded key blindly.
The official resolute `omc` package currently declares compiler/build dependencies;
these are APT dependencies, not a bootstrap build-profile edge. GUI recommendations
and the `openmodelica` metapackage are not selected.
