# Create virtual env
virtualenv env

# Running influxdb and grafana
docker run -d --name=influxdb -p 8086:8086 -v .:/var/lib/influxdb influxdb
docker run -d --name=grafana -p 3000:3000 grafana/grafana

# Rename source directory to repo name
