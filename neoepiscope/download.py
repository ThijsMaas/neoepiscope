class RailRnaInstaller(object):
    """ Installs Rail-RNA and its assorted dependencies.

        Init vars
        -------------
        zip_name: path to (currently executing) zip containing Rail-RNA
        curl_exe: path to cURL executable; if None, use 'curl'
        install_dir: path to install dir; if None, use home directory
            + 'raildotbio' if installing for self and /usr/local/raildotbio if
            installing for all users
        no_dependencies: if True, install Rail-RNA and none of its dependencies
        prep_dependencies: if True, only installs dependencies needed for
            Rail-RNA's preprocess job flow; overrided by no_dependencies
        yes: if True, answer yes to all questions automatically
        add_symlinks: adds symlinks for all installed dependencies
            to /usr/local/bin if installing for all users. Useful in elastic
            mode so paths to installed dependencies need not be specified
    """

    def __init__(self, zip_name, curl_exe=None, install_dir=None,
                    no_dependencies=False, prep_dependencies=False,
                    yes=False, me=False, add_symlinks=False,
                    print_log_on_error=False):
        print_to_screen(u"""{0} Rail-RNA v{1} Installer""".format(
                                        u'\u2200', version_number)
                                    )
        if sys.platform in ['linux', 'linux2']:
            if os.path.isfile('/mnt/var/lib/info/instance.json'):
                # Assume an EMR cluster and prepend S3 download URLs
                self.depends = dependency_urls.ec2_dependencies
            else:
                self.depends = dependency_urls.linux_dependencies
        elif sys.platform == 'darwin':
            self.depends = dependency_urls.mac_dependencies
        else:
            print_to_screen(
                    'Rail-RNA cannot be installed because it is not supported '
                    'by your OS. Currently supported OSes are Mac OS X and '
                    'Linux.'
                )
            sys.exit(1)
        self.install_dir = install_dir
        self.no_dependencies = no_dependencies
        self.zip_name = os.path.abspath(zip_name)
        self.curl_exe = curl_exe
        log_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(log_dir, 'rail-rna_install.log')
        self.log_stream = open(self.log_file, 'w')
        self.finished = False
        register_cleanup(remove_temporary_directories, [log_dir])
        self.yes = yes or me
        self.me = me
        self.prep_dependencies = prep_dependencies
        self.add_symlinks = add_symlinks
        self.print_log_on_error = print_log_on_error

    def __enter__(self):
        return self

    def _print_to_screen_and_log(self, message, **kwargs):
        print >>self.log_stream, message
        print_to_screen(message, **kwargs)

    def _bail(self):
        """ Copy log to some temporary dir and GTFO. """
        new_log_file = os.path.join(tempfile.mkdtemp(),
                                            'rail-rna_installer.log')
        shutil.copyfile(self.log_file, new_log_file)
        if self.print_log_on_error:
            print_to_screen('Installation log (also at %s):' % new_log_file)
            print_to_screen('===')
            with open(new_log_file, 'r') as log_fh:
                for ln in log_fh:
                    print_to_screen(ln.rstrip())
            print_to_screen('===')
        else:
            print_to_screen('Installation log may be found at %s.' % new_log_file)
        sys.exit(1)

    def _yes_no_query(self, question, answer=None):
        """ Gets a yes/no answer from the user if self.yes is not True.

            question: string with question to be printed to console
            answer: boolean that overrides self.yes if an answer should
                be forced

            Return value: boolean
        """
        if answer is None:
            if self.yes:
                print '%s [y/n]: y' % question
                return True
        elif answer:
            print '%s [y/n]: y' % question
            return True
        else:
            print '%s [y/n]: n' % question
            return False
        while True:
            sys.stdout.write('%s [y/n]: ' % question)
            try:
                try:
                    return strtobool(raw_input().lower())
                except KeyboardInterrupt:
                    sys.stdout.write('\n')
                    sys.exit(0)
            except ValueError:
                sys.stdout.write('Please enter \'y\' or \'n\'.\n')

    def _add_symlink_to_exe(self, exe_path):
        """ Adds symlinks to dependency executable; works only if sudo'd

            exe_path: path to executable

            No return value
        """
        self._print_to_screen_and_log(
                    '[Installing] Creating symlinks to dependencies...',
                    newline=False, carriage_return=True
                )
        symlink_command = ['ln', '-s', exe_path, '/usr/local/bin']
        try:
            subprocess.check_output(symlink_command, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            if 'file exists' in e.output.lower():
                self._print_to_screen_and_log(
                        ('[Warning] /usr/local/bin/%s already exists; '
                         'skipping symlink creation.')
                            % os.path.basename(exe_path),
                        newline=True, carriage_return=False
                    )
                self._print_to_screen_and_log(
                    '[Installing] Creating symlinks to dependencies...',
                    newline=False, carriage_return=True
                )
            else:
                print >>self.log_stream, e.output
                self._print_to_screen_and_log(
                            ('Error encountered symlinking; exit code was %d; '
                             'command invoked was "%s".') %
                                (e.returncode, ' '.join(symlink_command))
                        )
                self._bail()

    def _grab_and_explode(self, urls, name):
        """ Special method for grabbing and exploding a package, if necessary.

            Does not verify URLs since these are preverified. Package is
            downloaded to current directory.

            url: list of urls to grab
            name: name of download

            No return value
        """
        self._print_to_screen_and_log('[Installing] Downloading %s...' % name,
                                        newline=False,
                                        carriage_return=True)
        url_deque = deque(urls)
        while url_deque:
            url = url_deque.popleft()
            '''Follow redirects (-L), write to file (-O), respect
            content disposition'''
            command = [self.curl_exe, '-L', '-O', url]
            filename = url.rpartition('/')[2]
            print >>self.log_stream, 'Downloading {} from {}...'.format(
                                                                    name, url
                                                                )
            try:
                subprocess.check_output(command, stderr=self.log_stream)
            except subprocess.CalledProcessError as e:
                if not url_deque:
                    self._print_to_screen_and_log(
                            ('Error encountered downloading file %s; exit '
                             'code was %d; command invoked was "%s".') %
                                (url, e.returncode, ' '.join(command))
                        )
                    self._print_to_screen_and_log(
                            'Make sure web access is available.'
                        )
                    self._bail()
                else:
                    self._print_to_screen_and_log(
                        '[Installing] Download failed; '
                        'trying alternate URL for %s...' % name,
                        newline=False,
                        carriage_return=True
                    )
            else:
                # Explode
                explode_command = None
                if url[-8:] == '.tar.bz2':
                    explode_command = ['tar', 'xvjf', filename]
                elif url[-7:] == '.tar.gz' or url[-4:] == '.tgz':
                    explode_command = ['tar', 'xvzf', filename]
                elif url[-4:] == '.zip':
                    self._print_to_screen_and_log(
                            '[Installing] Extracting %s...' % name,
                            newline=False,
                            carriage_return=True)
                    try:
                        with zipfile.ZipFile(filename) as zip_object:
                            zip_object.extractall()
                    except Exception as e:
                        if not url_deque:
                            self._print_to_screen_and_log(
                                    'Error encountered exploding %s.'
                                        % filename
                                )
                            self._bail()
                        else:
                            self._print_to_screen_and_log(
                                '[Installing] Extraction failed; '
                                'trying alternate URL for %s...' % name,
                                newline=False,
                                carriage_return=True
                            )
                            continue
                    finally:
                        os.remove(filename)
                if explode_command is not None:
                    self._print_to_screen_and_log(
                            '[Installing] Extracting %s...' % name,
                            newline=False,
                            carriage_return=True)
                    try:
                        subprocess.check_output(explode_command,
                                                stderr=self.log_stream)
                    except subprocess.CalledProcessError as e:
                        if not url_deque:
                            self._print_to_screen_and_log(
                                ('Error encountered exploding file %s; exit '
                                 'code was %d; command invoked was "%s".') %
                                (filename, e.returncode,
                                    ' '.join(explode_command))
                            )
                            self._bail()
                        else:
                            self._print_to_screen_and_log(
                                '[Installing] Extraction failed; '
                                'trying alternate URL for %s...' % name,
                                newline=False,
                                carriage_return=True
                            )
                            continue
                    finally:
                        os.remove(filename)
                break

    def _quote(self, path=None):
        """ Decks path with single quotes if it's not None

            path: path or None

            Return value: None if path is None, else path decked by single
                quotes
        """
        if path is None:
            return 'None'
        return "'%s'" % path

    def install(self):
        """ Installs Rail-RNA and all its dependencies. """
        if not self.no_dependencies and self.curl_exe is None:
            self.curl_exe = which('curl')
            if self.curl_exe is None:
                print_to_screen('Rail-RNA\'s installer requires Curl if '
                                'dependencies are to be installed. '
                                'Download it at '
                                'http://curl.haxx.se/download.html and use '
                                '--curl to specify its path, or '
                                'disable installing dependencies with '
                                '--no-dependencies.')
                sys.exit(1)
        if self._yes_no_query(
                'Rail-RNA can be installed for all users or just the '
                'current user.\n    * Install for all users?',
                answer=(None if not self.yes else (self.yes and not self.me))
            ):
            if os.getuid():
                print_to_screen('Rerun with sudo privileges to install '
                                'for all users.')
                sys.exit(0)
            install_dir = '/usr/local'
            self.local = False
        else:
            install_dir = os.path.abspath(os.path.expanduser('~/'))
            self.local = True
        bin_dir = os.path.join(install_dir, 'bin')
        rail_exe = os.path.join(bin_dir, 'rail-rna')
        if self.install_dir is None:
            self.final_install_dir = os.path.join(install_dir, 'raildotbio')
        else:
            # User specified an installation directory
            self.final_install_dir = self.install_dir
        # Install in a temporary directory first, then move to final dest
        temp_install_dir = tempfile.mkdtemp()
        register_cleanup(remove_temporary_directories, [temp_install_dir])
        if os.path.exists(self.final_install_dir):
            if self._yes_no_query(
                    ('The installation path {dir} already exists.\n    '
                    '* Overwrite {dir}?').format(dir=self.final_install_dir)
                ):
                try:
                    shutil.rmtree(self.final_install_dir)
                except OSError:
                    # Handle this later if directory creation fails
                    pass
                try:
                    os.remove(self.final_install_dir)
                except OSError:
                    pass
            else:
                print_to_screen(
                        'Specify a different installation directory with '
                        '--install-dir.'
                    )
                sys.exit(0)
        self._print_to_screen_and_log('[Installing] Extracting Rail-RNA...',
                                        newline=False,
                                        carriage_return=True)
        try:
            os.makedirs(self.final_install_dir)
        except OSError as e:
            self._print_to_screen_and_log(
                            ('Problem encountered trying to create '
                             'directory %s for installation. May need '
                             'sudo permissions.') % self.final_install_dir
                        )
            self._bail()
        else:
            # So it's possible to move temp installation dir there
            os.rmdir(self.final_install_dir)
            pass
        with cd(temp_install_dir):
            with zipfile.ZipFile(self.zip_name) as zip_object:
                zip_object.extractall('./rail-rna')
            if not self.no_dependencies:
                self._grab_and_explode(self.depends['pypy'], 'PyPy')
                self._grab_and_explode(self.depends['sra_tools'], 'SRA Tools')
                if not self.prep_dependencies:
                    self._grab_and_explode(self.depends['bowtie1'], 'Bowtie 1')
                    self._grab_and_explode(self.depends['bowtie2'], 'Bowtie 2')
                    self._grab_and_explode(self.depends['bedgraphtobigwig'],
                                            'BedGraphToBigWig')
                    self._grab_and_explode(self.depends['samtools'],
                                                                'SAMTools')
            if not self.prep_dependencies and not self.no_dependencies:
                # Have to make SAMTools (annoying; maybe change this)
                samtools_dir = os.path.join(temp_install_dir,
                        self.depends['samtools'][0].rpartition('/')[2][:-8]
                    )
                with cd(samtools_dir):
                    '''Make sure unistd.h is #included cram_io.c ... it's some
                    bug in some SAMTools that prevents compilation on
                    langmead-fs1, which may be a general problem with
                    portability. See https://github.com/samtools/htslib/commit/
                    0ec5202de5691b27917ce828a9d24c9c729a9b81'''
                    cram_io_file = os.path.join(glob.glob('./htslib-*')[0],
                                                    'cram', 'cram_io.c')
                    with open(cram_io_file) as cram_io_stream:
                        all_cram_io = cram_io_stream.read()
                    if '<unistd.h>' not in all_cram_io:
                        with open(cram_io_file, 'w') as cram_io_out_stream:
                            cram_io_out_stream.write(all_cram_io.replace(
                                    '#include <string.h>',
                                    '#include <string.h>\n#include <unistd.h>'
                                ))
                    makefile = 'Makefile'
                    with open(makefile) as makefile_stream:
                        all_makefile = makefile_stream.read()
                    with open(makefile, 'w') as makefile_stream:
                        makefile_stream.write(
                            all_makefile.replace(
                                    '-D_CURSES_LIB=1', '-D_CURSES_LIB=0'
                                ).replace('LIBCURSES=','#LIBCURSES=')
                        )
                    # Make on all but one cylinder
                    thread_count = max(1, multiprocessing.cpu_count() - 1)
                    samtools_command = ['make', '-j%d' % thread_count]
                    self._print_to_screen_and_log(
                                '[Installing] Making SAMTools...',
                                newline=False,
                                carriage_return=True
                            )
                    try:
                        subprocess.check_output(samtools_command,
                                                    stderr=self.log_stream)
                    except subprocess.CalledProcessError as e:
                        self._print_to_screen_and_log(
                                ('Error encountered making SAMTools; exit '
                                 'code was %d; command invoked was "%s".') %
                                    (e.returncode, ' '.join(samtools_command))
                            )
                        self._bail()
                samtools = os.path.join(self.final_install_dir,
                        self.depends['samtools'][0].rpartition('/')[2][:-8],
                        'samtools')

                def get_immediate_subdirectories(dr):
                    return [name for name in os.listdir(dr)
                            if os.path.isdir(os.path.join(dr, name))]

                bowtie1_toks = self.depends['bowtie1'][0].rpartition(
                            '/'
                        )[2].split('-')
                for i in [2, 3, 4]:
                    bowtie1_base = '-'.join(bowtie1_toks[:i])
                    if bowtie1_base.endswith('.zip'):
                        bowtie1_base = bowtie1_base[:-4]
                    bowtie1_tmp = os.path.join(bowtie1_base, 'bowtie')
                    if os.path.exists(bowtie1_tmp):
                        break
                bowtie1_build_tmp = os.path.join(bowtie1_base, 'bowtie-build')

                if not os.path.exists(bowtie1_tmp) or not os.path.exists(bowtie1_build_tmp):
                    raise RuntimeError('Exploding bowtie package failed to '
                                       'create appropriately named directory: '
                                       + get_immediate_subdirectories('.'))

                bowtie1 = os.path.join(self.final_install_dir,
                                       bowtie1_base, 'bowtie')
                bowtie1_build = os.path.join(self.final_install_dir,
                                             bowtie1_base, 'bowtie-build')

                bowtie2_toks = self.depends['bowtie2'][0].rpartition(
                            '/'
                        )[2].split('-')
                for i in [2, 3, 4]:
                    bowtie2_base = '-'.join(bowtie2_toks[:i])
                    if bowtie2_base.endswith('.zip'):
                        bowtie2_base = bowtie2_base[:-4]
                    bowtie2_tmp = os.path.join(bowtie2_base, 'bowtie2')
                    if os.path.exists(bowtie2_tmp):
                        break
                bowtie2_build_tmp = os.path.join(bowtie2_base, 'bowtie2-build')

                if not os.path.exists(bowtie2_tmp) or not os.path.exists(bowtie2_build_tmp):
                    raise RuntimeError('Exploding bowtie2 package failed to '
                                       'create appropriately named directory: '
                                       + get_immediate_subdirectories('.'))

                bowtie2 = os.path.join(self.final_install_dir,
                                       bowtie2_base, 'bowtie2')
                bowtie2_build = os.path.join(self.final_install_dir,
                                             bowtie2_base, 'bowtie2-build')

                bedgraphtobigwig = os.path.join(
                                                self.final_install_dir,
                                                'bedGraphToBigWig'
                                            )
            else:
                bowtie1 = bowtie1_build = bowtie2 = bowtie2_build \
                    = bedgraphtobigwig = samtools = 'None'
            if self.no_dependencies:
                pypy = 'None'
                fastq_dump = 'None'
                vdb_config = 'None'
            else:
                pypy = os.path.join(self.final_install_dir,
                        self.depends['pypy'][0].rpartition(
                                '/'
                            )[2][:-8], 'bin', 'pypy'
                    )
                fastq_dump = os.path.join(self.final_install_dir,
                                self.depends['sra_tools'][0].rpartition(
                                '/'
                            )[2][:-7], 'bin', 'fastq-dump'
                    )
                vdb_config = os.path.join(self.final_install_dir,
                                self.depends['sra_tools'][0].rpartition(
                                '/'
                            )[2][:-7], 'bin', 'vdb-config'
                    )
            # Write paths to exe_paths
            with open(
                            os.path.join(temp_install_dir, 'rail-rna',
                                            'exe_paths.py'), 'w'
                        ) as exe_paths_stream:
                print >>exe_paths_stream, (
"""\"""
exe_paths.py
Part of Rail-RNA

Defines default paths of Rail-RNA's executable dependencies. Set a given
variable equal to None if the default path should be in PATH.
\"""

pypy = {pypy}
aws = None
curl = None
sort = None
bowtie1 = {bowtie1}
bowtie1_build = {bowtie1_build}
bowtie2 = {bowtie2}
bowtie2_build = {bowtie2_build}
samtools = {samtools}
bedgraphtobigwig = {bedgraphtobigwig}
fastq_dump = {fastq_dump}
vdb_config = {vdb_config}
"""
                ).format(pypy=self._quote(pypy), bowtie1=self._quote(bowtie1),
                            bowtie1_build=self._quote(bowtie1_build),
                            bowtie2=self._quote(bowtie2),
                            bowtie2_build=self._quote(bowtie2_build),
                            samtools=self._quote(samtools),
                            bedgraphtobigwig=self._quote(bedgraphtobigwig),
                            fastq_dump=self._quote(fastq_dump),
                            vdb_config=self._quote(vdb_config))
        # Move to final directory
        try:
            shutil.move(temp_install_dir, self.final_install_dir)
        except Exception as e:
            self._print_to_screen_and_log(('Problem "%s" encountered moving '
                                           'temporary installation directory '
                                           '%s to final destination %s.') % (
                                                e,
                                                temp_install_dir,
                                                self.final_install_dir
                                            ))
            self._bail()
        # Create shell-script executable
        try:
            os.makedirs(bin_dir)
        except Exception as e:
            if not os.path.isdir(bin_dir):
                self._print_to_screen_and_log(('Problem "%s" encountered '
                                               'creating directory %s.') % (
                                                    e,
                                                    bin_dir
                                                )
                                            )
                self._bail()
        install_dir_replacement = os.path.join(
                                self.final_install_dir, 'rail-rna'
                            )
        with open(rail_exe, 'w') as rail_exe_stream:
            print >>rail_exe_stream, (
"""#!/usr/bin/env bash

{python_executable} {install_dir} $@
"""
                ).format(python_executable=sys.executable,
                            install_dir=install_dir_replacement)
        if self.local:
            '''Have to add Rail to PATH. Do this in bashrc and bash_profile
            contingent on whether it's present already because of
            inconsistent behavior across Mac OS and Linux distros.'''
            to_print = (
"""
## Rail-RNA additions
if [ -d "{bin_dir}" ] && [[ ":$PATH:" != *":{bin_dir}:"* ]]; then
    PATH="${{PATH:+"$PATH:"}}{bin_dir}"
fi
export RAILDOTBIO={install_dir}
## End Rail-RNA additions
"""
                ).format(bin_dir=bin_dir,
                            install_dir=install_dir_replacement)
        else:
            # Just define raildotbio directory
            to_print = (
"""
## Rail-RNA addition
export RAILDOTBIO={install_dir}
## End Rail-RNA addition
"""
                ).format(bin_dir=bin_dir,
                            install_dir=install_dir_replacement)
        import mmap
        bashrc = os.path.expanduser('~/.bashrc')
        bash_profile = os.path.expanduser('~/.bash_profile')
        try:
            with open(bashrc) as bashrc_stream:
                mmapped = mmap.mmap(bashrc_stream.fileno(), 0, 
                                        access=mmap.ACCESS_READ)
                if mmapped.find(to_print) == -1:
                    print_to_bashrc = True
                else:
                    print_to_bashrc = False
        except (IOError, ValueError):
            # No file
            print_to_bashrc = True
        try:
            with open(bash_profile) as bash_profile_stream:
                mmapped = mmap.mmap(bash_profile_stream.fileno(), 0, 
                                        access=mmap.ACCESS_READ)
                if mmapped.find(to_print) == -1:
                    print_to_bash_profile = True
                else:
                    print_to_bash_profile = False
        except (IOError, ValueError):
            # No file
            print_to_bash_profile = True
        if print_to_bashrc:
            with open(bashrc, 'a') as bashrc_stream:
                print >>bashrc_stream, to_print
        if print_to_bash_profile:
            with open(bash_profile, 'a') as bash_profile_stream:
                print >>bash_profile_stream, to_print
        # Set 755 permissions across Rail's dirs and 644 across files
        dir_command = ['find', self.final_install_dir, '-type', 'd',
                            '-exec', 'chmod', '755', '{}', ';']
        file_command = ['find', self.final_install_dir, '-type', 'f',
                            '-exec', 'chmod', '644', '{}', ';']
        try:
            subprocess.check_output(dir_command,
                                        stderr=self.log_stream)
        except subprocess.CalledProcessError as e:
            self._print_to_screen_and_log(
                        ('Error encountered changing directory '
                         'permissions; exit code was %d; command invoked '
                         'was "%s".') %
                            (e.returncode, ' '.join(dir_command))
                    )
            self._bail()
        try:
            subprocess.check_output(file_command,
                                        stderr=self.log_stream)
        except subprocess.CalledProcessError as e:
            self._print_to_screen_and_log(
                        ('Error encountered changing file '
                         'permissions; exit code was %d; command invoked '
                         'was "%s".') %
                            (e.returncode, ' '.join(file_command))
                    )
            self._bail()
        # Go back and set 755 permissions for executables
        os.chmod(rail_exe, 0755)
        if not self.no_dependencies:
            os.chmod(pypy, 0755)
            os.chmod(fastq_dump, 0755)
            os.chmod(vdb_config, 0755)
            if not self.prep_dependencies:
                for program in [bowtie1, bowtie1_build, bowtie2, bowtie2_build,
                                samtools, bedgraphtobigwig]:
                    os.chmod(program, 0755)
                    # Also for misc. Bowtie executables
                    for program in glob.glob(
                            os.path.join(os.path.dirname(bowtie1), 'bowtie-*')
                        ):
                        os.chmod(program, 0755)
                    for program in glob.glob(
                            os.path.join(os.path.dirname(bowtie2), 'bowtie2-*')
                        ):
                        os.chmod(program, 0755)
            if self.add_symlinks:
                # Write appropriate symlinks
                self._add_symlink_to_exe(pypy)
                self._add_symlink_to_exe(fastq_dump)
                self._add_symlink_to_exe(vdb_config)
                if not self.prep_dependencies:
                    for program in [bowtie1, bowtie1_build, bowtie2,
                                    bowtie2_build, samtools, bedgraphtobigwig]:
                        self._add_symlink_to_exe(program)
        self._print_to_screen_and_log('Installed Rail-RNA.')
        # ipyparallel much?
        try:
            import ipyparallel
        except ImportError:
            # Guess not
            if self._yes_no_query(
                    'IPython Parallel is not installed but required for '
                    'Rail-RNA to work in its "parallel" mode.\n'
                    '    * Install IPython Parallel now?'
                ):
                temp_ipython_install_dir = tempfile.mkdtemp()
                register_cleanup(remove_temporary_directories,
                                    [temp_ipython_install_dir])
                with cd(temp_ipython_install_dir):
                    self._grab_and_explode(
                        self.depends['ipython'], 'IPython Parallel')
                    setup_dir = os.path.dirname(find('setup.py', './'))
                    with cd(setup_dir):
                        ipython_command = [
                                    sys.executable, 'setup.py', 'install',
                                ]
                        if self.local:
                            ipython_command.append('--user')
                        try:
                            subprocess.check_output(ipython_command,
                                                        stderr=self.log_stream)
                        except subprocess.CalledProcessError as e:
                            self._print_to_screen_and_log(
                                ('Error encountered installing IPython '
                                 'Parallel; exit code was %d; command '
                                 'invoked was "%s".') %
                                    (e.returncode, ' '.join(ipython_command))
                            )
                            self._bail()
        install_aws = (not self.no_dependencies and not which('aws'))
        self.installed_aws = False
        if install_aws and self._yes_no_query(
                'AWS CLI is not installed but required for Rail-RNA to work '
                'in its "elastic" mode, on Amazon Elastic MapReduce.\n'
                '    * Install AWS CLI now?'
            ):
            temp_aws_install_dir = tempfile.mkdtemp()
            register_cleanup(remove_temporary_directories,
                                [temp_aws_install_dir])
            with cd(temp_aws_install_dir):
                self._grab_and_explode(self.depends['aws_cli'], 'AWS CLI')
                os.chmod('./awscli-bundle/install', 0755)
                if self.local:
                    # Local install
                    aws_command = ['./awscli-bundle/install', '-b',
                                    os.path.join(bin_dir, 'aws'),
                                   '-i', os.path.abspath(
                                        os.path.expanduser('~/.local/lib/aws')
                                    )]
                else:
                    # All users
                    aws_command = ['./awscli-bundle/install',
                                    '-i', '/usr/local/aws',
                                    '-b', '/usr/local/bin/aws']
                try:
                    subprocess.check_output(aws_command,
                                                stderr=self.log_stream)
                except (OSError, subprocess.CalledProcessError) as e:
                    self._print_to_screen_and_log(
                            ('Error encountered installing AWS CLI; exit '
                             'code was %d; command invoked was "%s".') %
                                (e.returncode, ' '.join(aws_command))
                        )
                    self._bail()
            self.installed_aws = True
        elif install_aws:
            print_to_screen('Visit http://docs.aws.amazon.com/cli/latest/'
                            'userguide/installing.html to install the '
                            'AWS CLI later.')
        self.finished = True