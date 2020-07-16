# Copr does not have Git available. Install it before anything else.
INSTALLER := $(shell [ -f /usr/bin/dnf ] && echo dnf || echo yum)
INSTALL_GIT := $(shell [ -f /usr/bin/git ] || $(INSTALLER) -y install git)
INSTALL_ANSIBLE := $(shell [ -f /usr/bin/ansible-galaxy ] || $(INSTALLER) -y install ansible)

NAME = ansible-collection-ktdreyer-koji-ansible

BASE_COMMIT := $(shell git rev-list --max-parents=0 HEAD)
REV_LIST := $(shell git rev-list --count $(BASE_COMMIT)..HEAD)
COMMIT_COUNT := $(shell echo $$(( $(REV_LIST) - 1 )))
VERSION := 0.0.$(COMMIT_COUNT)

# Copr will override this:
outdir = .


srpm: tar spec
	rpmbuild -bs $(NAME).spec \
	  --define "_topdir ." \
	  --define "_sourcedir ." \
	  --define "_srcrpmdir $(outdir)" \
	  --define "dist .el8"

spec:
	sed .copr/$(NAME).spec.in -e "s/{{ version }}/$(VERSION)/" > $(NAME).spec

tar:
	rpm -qv pandoc || $(INSTALLER) -y install pandoc && \
	./build-collection && \
	mv _build/ktdreyer-koji_ansible-$(VERSION).tar.gz .

clean:
	rm -rf _build/
	rm -f ktdreyer-koji_ansible-*.tar.gz
	rm -f $(NAME)-*.src.rpm

.PHONY: dist srpm spec tar
