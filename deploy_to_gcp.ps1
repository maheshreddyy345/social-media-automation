$instance = "social-media-bot"
$zone = "us-central1-a"

$remote = @'
set -e
cd /home/bot
git pull origin main
source /home/bot/venv/bin/activate
pip install -r requirements.txt
pip install crewai langchain-xai psycopg2-binary SQLAlchemy duckduckgo-search python-dotenv requests anthropic apscheduler pyyaml
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart social-media-bot.service || true
sudo systemctl enable --now openclaw.service reply-scheduler.service
sudo systemctl enable --now reply-scanner-bjp.timer reply-scanner-kw.timer reply-scanner-tr.timer
sudo systemctl restart reply-scheduler.service
'@

Write-Host "Syncing repo + installing deps + refreshing systemd units..."
gcloud compute ssh $instance --zone $zone --quiet --command $remote

Write-Host "Deployment to Cloud Complete!"
