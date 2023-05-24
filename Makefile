include /usr/share/dpkg/pkg-info.mk

PACKAGE=pve-edk2-firmware

SRCDIR=edk2
BUILDDIR ?= $(PACKAGE)-$(DEB_VERSION_UPSTREAM)
ORIG_SRC_TAR=$(PACKAGE)_$(DEB_VERSION_UPSTREAM).orig.tar.gz

GITVERSION:=$(shell git rev-parse HEAD)

DEB=$(PACKAGE)_$(DEB_VERSION)_all.deb
DSC=$(PACKAGE)_$(DEB_VERSION).dsc

all: $(DEB)
	@echo $(DEB)

$(BUILDDIR): $(SRCDIR)/Readme.md
	rm -rf $(BUILDDIR)
	cp -rpa $(SRCDIR) $(BUILDDIR)
	cp -a debian $(BUILDDIR)
	echo "git clone git://git.proxmox.com/git/pve-edk2-firmware.git\\ngit checkout $(GITVERSION)" > $(BUILDDIR)/debian/SOURCE

.PHONY: deb
deb: $(DEB)
$(DEB): $(BUILDDIR)
	cd $(BUILDDIR); dpkg-buildpackage -b -uc -us
	lintian $(DEB)
	@echo $(DEB)

$(ORIG_SRC_TAR): $(BUILDDIR)
	tar czf $(ORIG_SRC_TAR) --exclude="$(BUILDDIR)/debian" $(BUILDDIR)

$(DSC): $(BUILDDIR) $(ORIG_SRC_TAR)
	cd $(BUILDDIR); dpkg-buildpackage -S -uc -us -d

sbuild: $(DSC)
	sbuild $(DSC)

.PHONY: dsc
dsc: $(DSC)
	$(MAKE) clean
	$(MAKE) $(DSC)
	lintian $(DSC)

.PHONY: submodule
submodule:
	test -e edk2/Maintainers.txt || git submodule update --init --recursive

$(SRCDIR)/Readme.md: submodule

.PHONY: update_modules
update_modules: submodule
	git submodule foreach 'git pull --ff-only origin master'

.PHONY: upload
upload: UPLOAD_DIST ?= $(DEB_DISTRIBUTION)
upload: $(DEB)
	tar cf - $(DEB)|ssh -X repoman@repo.proxmox.com -- upload --product pve --dist $(UPLOAD_DIST)

.PHONY: distclean clean
distclean: clean
clean:
	rm -rf *.deb $(PACKAGE)-[0-9]*/ $(PACKAGE)*.tar* *.changes *.dsc *.buildinfo *.build

.PHONY: dinstall
dinstall: $(DEB)
	dpkg -i $(DEB)
