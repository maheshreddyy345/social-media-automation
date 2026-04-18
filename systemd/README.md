# Systemd units — Cold Open reply bot

One-time setup on the VM (after `git pull` has landed these files under `/home/bot/social-media-automation/systemd/`):

```bash
sudo cp /home/bot/social-media-automation/systemd/*.service /etc/systemd/system/
sudo cp /home/bot/social-media-automation/systemd/*.timer   /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable --now openclaw.service
sudo systemctl enable --now reply-scheduler.service
sudo systemctl enable --now reply-scanner-bjp.timer
sudo systemctl enable --now reply-scanner-kw.timer
sudo systemctl enable --now reply-scanner-tr.timer
```

OpenClaw first-time login (required before the scheduler can post):

```bash
# From your laptop, with X11 or VNC forwarding:
ssh -L 5900:localhost:5900 bot@34.63.251.46
openclaw login --session twitter-main   # log into x.com as @GetColdOpen, close when done
openclaw session list                   # confirm twitter-main is persistent
```

Kill switch:

```bash
# Immediate stop
sudo systemctl stop reply-scheduler.service
# OR flip the env and restart — safer for in-flight drafts
sed -i 's/^REPLY_BOT_ENABLED=.*/REPLY_BOT_ENABLED=false/' /home/bot/social-media-automation/.env
sudo systemctl restart reply-scheduler.service
```

Logs:

```bash
journalctl -u reply-scheduler.service -f
journalctl -u reply-scanner-bjp.service --since "1 hour ago"
journalctl -u openclaw.service -f
```
