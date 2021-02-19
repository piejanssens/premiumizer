[global]
server_port = 5000
bind_ip = 0.0.0.0
reverse_proxy_path =
custom_domain =
active_interval = 3
idle_interval = 300
debug_enabled = 0

[security]
login_enabled = 0
username =
password =

[premiumize]
apikey =

[downloads]
time_shed = 0
time_shed_start = 00:00
time_shed_stop = 06:00
download_enabled = 0
download_all = 0
download_rss = 0
download_max = 1
download_threads = 1
download_speed = -1
remove_cloud = 0
remove_cloud_delay = 0
seed_torrent = 0
download_location =
nzbtomedia_location = [Change to path]\nzbToMedia.py
jd_enabled = 0
jd_username =
jd_password =
jd_device_name =
aria2_enabled = 0
aria2_host = localhost
aria2_port = 6800
aria2_secret = premiumizer

[categories]
cat_name[1] = tv
cat_dir[1] =
cat_ext[1] =
cat_ext_blacklist[1] = 0
cat_delsample[1] = 0
cat_nzbtomedia[1] = 0
cat_name[2] = movie
cat_dir[2] =
cat_ext[2] =
cat_ext_blacklist[2] = 0
cat_delsample[2] = 0
cat_nzbtomedia[2] = 0
cat_name[3] =
cat_dir[3] =
cat_ext[3] =
cat_ext_blacklist[3] = 0
cat_delsample[3] = 0
cat_nzbtomedia[3] = 0
cat_name[4] =
cat_dir[4] =
cat_ext[4] =
cat_ext_blacklist[4] = 0
cat_delsample[4] = 0
cat_nzbtomedia[4] = 0
cat_name[5] =
cat_dir[5] =
cat_ext[5] =
cat_ext_blacklist[5] = 0
cat_delsample[5] = 0
cat_nzbtomedia[5] = 0
cat_name[6] = default
cat_dir[6] =
cat_ext[6] =
cat_ext_blacklist[6] = 0
cat_delsample[6] = 0
cat_nzbtomedia[6] = 0

[upload]
watchdir_enabled = 0
watchdir_location =
watchdir_walk_enabled = 0
watchdir_walk_interval = 60

[notifications]
email_enabled = 0
email_on_failure = 0
email_from =
email_to =
email_server =
email_port =
email_encryption = 0
email_username =
email_password =
apprise_enabled = 0
apprise_push_on_failure = 0
apprise_url = 

[update]
#Do not change these values#
updated = 1
auto_update = 0
update_date = Never
config_version = 2.9
req_version = 10.2
