#!/usr/bin/env python3
#
# Copyright 2019-2022 Canonical Ltd.
# Authors:
# - dann frazier <dann.frazier@canonical.com>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
#

import enum
import os
import pexpect
import subprocess
import sys
import time
import unittest

from UEFI.Filesystems import GrubShellBootableIsoImage
from UEFI.SignedBinary import SignedBinary
from UEFI.Qemu import QemuEfiMachine, QemuEfiVariant, QemuEfiFlashSize
from UEFI import Qemu

DPKG_ARCH = subprocess.check_output(
    ['dpkg', '--print-architecture']
).decode().rstrip()

EfiArchToGrubArch = {
    'X64': "x86_64",
    'AA64': "arm64",
}

TEST_TIMEOUT = 120


def get_local_grub_path(efi_arch, signed=False):
    grub_subdir = "%s-efi" % EfiArchToGrubArch[efi_arch.upper()]
    ext = "efi"
    if signed:
        grub_subdir = f"{grub_subdir}-signed"
        ext = f"{ext}.signed"

    grub_path = os.path.join(
        os.path.sep, 'usr', 'lib', 'grub',
        '%s' % (grub_subdir),
        "" if signed else "monolithic",
        'grub%s.%s' % (efi_arch.lower(), ext)
    )
    return grub_path


def get_local_shim_path(efi_arch, signed=False):
    ext = 'efi'
    if signed:
        ext = f"{ext}.signed"
    shim_path = os.path.join(
        os.path.sep, 'usr', 'lib', 'shim',
        'shim%s.%s' % (efi_arch.lower(), ext)
    )
    return shim_path


class BootToShellTest(unittest.TestCase):
    debug = True

    def setUp(self):
        self.startTime = time.time()

    def tearDown(self):
        t = time.time() - self.startTime
        sys.stdout.write("%s runtime: %.3fs\n" % (self.id(), t))

    def run_cmd_check_shell(self, cmd):
        child = pexpect.spawn(' '.join(cmd), encoding='UTF-8')

        if self.debug:
            child.logfile = sys.stdout
        try:
            while True:
                i = child.expect(
                    [
                        'Press .* or any other key to continue',
                        'Shell> '
                    ],
                    timeout=TEST_TIMEOUT,
                )
                if i == 0:
                    child.sendline('\x1b')
                    continue
                if i == 1:
                    child.sendline('reset -s\r')
                    continue
        except pexpect.EOF:
            child.close()
            if child.exitstatus != 0:
                self.fail("ERROR: exit code %d\n" % (child.exitstatus))
        except pexpect.TIMEOUT as err:
            self.fail("%s\n" % (err))

    def run_cmd_check_secure_boot(self, cmd, efiarch, should_verify):
        class State(enum.Enum):
            PRE_EXEC = 1
            POST_EXEC = 2

        child = pexpect.spawn(' '.join(cmd), encoding='UTF-8')

        if self.debug:
            child.logfile = sys.stdout
        try:
            state = State.PRE_EXEC
            while True:
                i = child.expect(
                    [
                        'Press .* or any other key to continue',
                        'Shell> ',
                        "FS0:\\\\> ",
                        'grub> ',
                        'Command Error Status: Access Denied',
                    ],
                    timeout=TEST_TIMEOUT,
                )
                if i == 0:
                    child.sendline('\x1b')
                    continue
                if i == 1:
                    child.sendline('fs0:\r')
                    continue
                if i == 2:
                    if state == State.PRE_EXEC:
                        child.sendline(f'\\efi\\boot\\boot{efiarch}.efi\r')
                        state = State.POST_EXEC
                    elif state == State.POST_EXEC:
                        child.sendline('reset -s\r')
                    continue
                if i == 3:
                    child.sendline('halt\r')
                    verified = True
                    continue
                if i == 4:
                    verified = False
                    continue
        except pexpect.EOF:
            child.close()
            if child.exitstatus != 0:
                self.fail("ERROR: exit code %d\n" % (child.exitstatus))
        except pexpect.TIMEOUT as err:
            self.fail("%s\n" % (err))
        self.assertEqual(should_verify, verified)

    def test_aavmf(self):
        q = Qemu.QemuCommand(QemuEfiMachine.AAVMF)
        self.run_cmd_check_shell(q.command)

    @unittest.skipUnless(DPKG_ARCH == 'arm64', "Requires grub-efi-arm64")
    @unittest.skipUnless(
        subprocess.run(
            ['dpkg-vendor', '--derives-from', 'Ubuntu']
        ).returncode == 0,
        "Debian does not provide a signed shim for arm64, see #992073"
    )
    def test_aavmf_ms_secure_boot_signed(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.AAVMF,
            variant=QemuEfiVariant.MS,
        )
        grub = get_local_grub_path('AA64', signed=True)
        shim = get_local_shim_path('AA64', signed=True)
        iso = GrubShellBootableIsoImage('AA64', shim, grub)
        q.add_disk(iso.path)
        self.run_cmd_check_secure_boot(q.command, 'aa64', True)

    @unittest.skipUnless(DPKG_ARCH == 'arm64', "Requires grub-efi-arm64")
    def test_aavmf_ms_secure_boot_unsigned(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.AAVMF,
            variant=QemuEfiVariant.MS,
        )
        grub = get_local_grub_path('AA64', signed=False)
        shim = get_local_shim_path('AA64', signed=False)
        iso = GrubShellBootableIsoImage('AA64', shim, grub)
        q.add_disk(iso.path)
        self.run_cmd_check_secure_boot(q.command, 'aa64', False)

    def test_aavmf_snakeoil(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.AAVMF,
            variant=QemuEfiVariant.SNAKEOIL,
        )
        self.run_cmd_check_shell(q.command)

    def test_aavmf32(self):
        q = Qemu.QemuCommand(QemuEfiMachine.AAVMF32)
        self.run_cmd_check_shell(q.command)

    def test_ovmf_4m(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            flash_size=QemuEfiFlashSize.SIZE_4MB,
        )
        self.run_cmd_check_shell(q.command)

    def test_ovmf_4m_secboot(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            variant=QemuEfiVariant.SECBOOT,
            flash_size=QemuEfiFlashSize.SIZE_4MB,
        )
        self.run_cmd_check_shell(q.command)

    def test_ovmf_4m_ms(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            variant=QemuEfiVariant.MS,
            flash_size=QemuEfiFlashSize.SIZE_4MB,
        )
        self.run_cmd_check_shell(q.command)

    def test_ovmf_snakeoil(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            variant=QemuEfiVariant.SNAKEOIL,
        )
        self.run_cmd_check_shell(q.command)

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_4m_ms_secure_boot_signed(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            variant=QemuEfiVariant.MS,
            flash_size=QemuEfiFlashSize.SIZE_4MB,
        )
        grub = get_local_grub_path('X64', signed=True)
        shim = get_local_shim_path('X64', signed=True)
        iso = GrubShellBootableIsoImage('X64', shim, grub)
        q.add_disk(iso.path)
        self.run_cmd_check_secure_boot(q.command, 'x64', True)

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_4m_ms_secure_boot_unsigned(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            variant=QemuEfiVariant.MS,
            flash_size=QemuEfiFlashSize.SIZE_4MB,
        )
        grub = get_local_grub_path('X64', signed=False)
        shim = get_local_shim_path('X64', signed=False)
        iso = GrubShellBootableIsoImage('X64', shim, grub)
        q.add_disk(iso.path)
        self.run_cmd_check_secure_boot(q.command, 'x64', False)

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_snakeoil_secure_boot_signed(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            variant=QemuEfiVariant.SNAKEOIL,
        )
        shim = SignedBinary(
            get_local_shim_path('X64', signed=False),
            "/usr/share/ovmf/PkKek-1-snakeoil.key",
            "/usr/share/ovmf/PkKek-1-snakeoil.pem",
            "snakeoil",
        )
        grub = SignedBinary(
            get_local_grub_path('X64', signed=False),
            "/usr/share/ovmf/PkKek-1-snakeoil.key",
            "/usr/share/ovmf/PkKek-1-snakeoil.pem",
            "snakeoil",
        )
        iso = GrubShellBootableIsoImage('X64', shim.path, grub.path)
        q.add_disk(iso.path)
        self.run_cmd_check_secure_boot(q.command, 'x64', True)

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_snakeoil_secure_boot_unsigned(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF_Q35,
            variant=QemuEfiVariant.SNAKEOIL,
            flash_size=QemuEfiFlashSize.DEFAULT,
        )
        grub = get_local_grub_path('X64', signed=False)
        shim = get_local_shim_path('X64', signed=False)
        iso = GrubShellBootableIsoImage('X64', shim, grub)
        q.add_disk(iso.path)
        self.run_cmd_check_secure_boot(q.command, 'x64', False)

    def test_ovmf32_4m_secboot(self):
        q = Qemu.QemuCommand(
            QemuEfiMachine.OVMF32,
            variant=QemuEfiVariant.SECBOOT,
            flash_size=QemuEfiFlashSize.SIZE_4MB,
        )
        self.run_cmd_check_shell(q.command)

    def test_riscv64(self):
        q = Qemu.QemuCommand(QemuEfiMachine.RISCV64)
        self.run_cmd_check_shell(q.command)

if __name__ == '__main__':
    unittest.main(verbosity=2)
