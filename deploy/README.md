# Host side of the skills sync (#42)

The seats keep their josui-skills checkouts current themselves
(`developer-skills-sync`, every `JOSUI_SKILLS_SYNC_INTERVAL` seconds). What a
host adds is the monitoring route: Nagios runs only on gloval, so each host
copies its seats' status lines to pCloud, where `check_skills_sync.sh`
(crunchtools/nagios-agent) reads them.

| Host | Checkouts | Marker(s) |
|------|-----------|-----------|
| Dolza | one, shared: Josui Prime mounts it read-write and syncs it, the seats mount it read-only and only relink | `dolza.shared` |
| Exedore | one per seat, `/srv/maxN/data/josui-skills`, synced inside each seat | `exedore.max1` … `exedore.max4` |

Install, as the user that runs the seats (rclone with a `pcloud:` remote is
already on both hosts):

```bash
install -Dm0755 deploy/skills-sync-push ~/.local/bin/skills-sync-push
install -Dm0644 deploy/<host>/skills-sync-push.{service,timer} -t ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now skills-sync-push.timer
```

On Exedore, check the unit's user can read a seat's status file, which the
seat writes 0644 from a container subuid: `head -1
/srv/max1/data/josui-skills/.git/skills-sync.status`.
