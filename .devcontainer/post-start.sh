service postgresql status
if [ "$?" -eq "1" ]; then
  echo "Postgres not installed. Postgres integration tests will fail for now."
else
  sudo service postgresql start
fi
