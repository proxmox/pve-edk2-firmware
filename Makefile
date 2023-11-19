include /usr/share/dpkg/pkg-info.mk

PACKAGE=pve-edk2-firmware

SRCDIR=edk2
BUILDDIR ?= $(PACKAGE)-$(DEB_VERSION_UPSTREAM)
ORIG_SRC_TAR=$(PACKAGE)_$(DEB_VERSION_UPSTREAM).orig.tar.gz

DSC=$(PACKAGE)_$(DEB_VERSION).dsc

# transitional virtual package depending on the amd64 ones
VIRTUAL_DEB = $(PACKAGE)_$(DEB_VERSION)_all.deb
AMD64_DEB = $(PACKAGE)-legacy_$(DEB_VERSION)_all.deb $(PACKAGE)-ovmf_$(DEB_VERSION)_all.deb
AARCH64_DEB = $(PACKAGE)-aarch64_$(DEB_VERSION)_all.deb
RISCV_DEB = $(PACKAGE)-riscv_$(DEB_VERSION)_all.deb

DEBS = $(VIRTUAL_DEB) $(AMD64_DEB) $(AARCH64_DEB) $(RISCV_DEB)

all: $(DEBS)
	@echo $(DEBS)

$(BUILDDIR): $(SRCDIR)/Readme.md
	rm -rf $@ $@.tmp
	cp -rpa $(SRCDIR) $@.tmp
	rm -rf $@.tmp/ArmPkg/Library/GccLto/*.a
	cp -a debian $@.tmp
	echo "git clone git://git.proxmox.com/git/pve-edk2-firmware.git\\ngit checkout $(shell git rev-parse HEAD)" > $@.tmp/debian/SOURCE
	mv $@.tmp $@

.PHONY: deb
deb: $(DEBS)
$(AMD64_DEB) $(AARCH64_DEB) $(RISCV_DEB): $(VIRTUAL_DEB)
$(VIRTUAL_DEB): $(BUILDDIR)
	cd $(BUILDDIR); dpkg-buildpackage -b -uc -us
	lintian $(DEBS)
	@echo $(DEBS)

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
upload: $(DEBS)
	tar cf - $(DEBS)|ssh -X repoman@repo.proxmox.com -- upload --product pve --dist $(UPLOAD_DIST)

.PHONY: distclean clean
distclean: clean
clean:
	rm -rf *.deb $(PACKAGE)-[0-9]*/ $(PACKAGE)*.tar* *.changes *.dsc *.buildinfo *.build

.PHONY: dinstall
dinstall: $(VIRTUAL_DEB) $(AMD64_DEB)
	dpkg -i $^
