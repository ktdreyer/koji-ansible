#!/bin/bash

set -eux

. tests/integration/functions.sh

sudo systemctl restart postgresql || sudo journalctl -xe

git clone --depth 1 https://pagure.io/koji.git
pushd koji
git log HEAD -1 --no-decorate
popd

# Create SSL certs
git clone --depth 1 https://pagure.io/koji-tools.git

pushd koji-tools
git log HEAD -1 --no-decorate
./src/bin/koji-ssl-admin new-ca --common-name "CI Koji CA"
./src/bin/koji-ssl-admin server-csr localhost
./src/bin/koji-ssl-admin sign localhost.csr

./src/bin/koji-ssl-admin user-csr admin
./src/bin/koji-ssl-admin sign admin.csr

# install client certs
mkdir -p ~/.koji/pki
cp koji-ca.crt ~/.koji/pki
mv admin.cert ~/.koji/pki/

# install hub certs
sudo cp koji-ca.crt /etc/ssl/certs/
sudo mv localhost.chain.crt /etc/ssl/certs/localhost.chain.crt
sudo mv localhost.key /etc/ssl/private/localhost.key
sudo chown root:ssl-cert /etc/ssl/private/localhost.key
sudo chmod 640 /etc/ssl/private/localhost.key

popd  # koji-tools

# Install/configure Koji client
mkdir -p ~/.koji/config.d/
cp -f tests/integration/ci.conf ~/.koji/config.d/
sed -e "s?%HOME%?$HOME?g" --in-place ~/.koji/config.d/ci.conf
# separate client profile to test without authentication:
# (If we call activate_session() with this profile, we will get an AuthError
# because no cert file exists for this profile.)
cp -f tests/integration/ci.conf ~/.koji/config.d/anonymous.conf
sed -e "s/^\\[ci\\]/[anonymous]/" -i ~/.koji/config.d/anonymous.conf
sed -e "/^cert = /d" -i ~/.koji/config.d/anonymous.conf
sed -e "s?%HOME%?$HOME?g" -i ~/.koji/config.d/anonymous.conf

# py2 -> py3 submitted upstream at https://pagure.io/koji/pull-request/1748
sed -i -e "s,/usr/bin/python2,/usr/bin/python3,g" koji/cli/koji


# set up koji-hub
sudo a2enmod actions wsgi ssl alias
sudo sed -i -e "s,www-data,$USER,g" /etc/apache2/envvars

# configure apache virtual hosts
sudo cp -f tests/integration/apache.conf /etc/apache2/sites-available/000-default.conf
sudo sed -e "s?%BUILD_DIR%?$(pwd)?g" --in-place /etc/apache2/sites-available/000-default.conf

# configuration to use our local kojihub Git clone
sed -i -e "s,/usr/share/koji-hub,$(pwd)/koji/kojihub/app,g" koji/kojihub/app/httpd.conf

sed -i -e "s,#DBHost = .*,DBHost = 127.0.0.1," koji/kojihub/app/hub.conf
sed -i -e "s,#DBPass = .*,DBPass = koji," koji/kojihub/app/hub.conf
sed -i -e "s,KojiDir = koji,KojiDir = $HOME/mnt/koji," koji/kojihub/app/hub.conf

mkdir -p $HOME/mnt/koji

reset_instance

cp tests/integration/ansible.cfg ~/.ansible.cfg
