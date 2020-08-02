

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.plug.utils import Zipfile

class Zipfile_bugfix(Zipfile):
    """
    Zipfile workaround. This class doesn't work with zip files in the recent release.
    pr-1068: replace file() -> open()
    """
    def extractall(self, path, members=None):
        """
        Extract all of the files in the zip into path.
        """
        import os
        names = self.zip_obj.namelist()
        for name in self.get_paths(names):
            fullname = os.path.join(path, name)
            if not os.path.exists(fullname):
                os.mkdir(fullname)
        for name in self.get_files(names):
            fullname = os.path.join(path, name)
            outfile = open(fullname, 'wb') # !!!!!
            outfile.write(self.zip_obj.read(name))
            outfile.close()


class ModuleProvider:
    """
    ModuleProvider
    ==============

    This class is used to load modules, and if necessary download them first.
    """
    def __init__(self, plugin_name, uistate):
        """
        Args:
            plugin_name (str): name of the plugin where this class is used
            uistate (): uistate for dialog
        """
        self.plugin_name = plugin_name
        self.uistate = uistate

    def check_for(self, module_name, module_version):
        """
        Check if a module is available.

        Args:
            module_name (str): module name
            module_version (str): module version

        Returns:
            Module: loaded module or None
        """
        import importlib
        import sys
        import os
        from gramps.gen.const import USER_PLUGINS
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, '__version__'):
                if module.__version__ != module_version:
                    raise ModuleNotFoundError()
        except ModuleNotFoundError:
            pass
        else:
            return module

        try:
            filename = os.path.join(
                USER_PLUGINS,
                self.plugin_name,
                module_name + '-' + module_version,
                module_name,
                '__init__.py')
            if os.path.isfile(filename):
                spec = importlib.util.spec_from_file_location(module_name, filename)
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
            else:
                raise FileNotFoundError(filename)
        except ModuleNotFoundError:
            pass
        except FileNotFoundError as e:
            pass
        else:
            return module
        return None

    def request(self, module_name, module_version, source_link):
        """
        Request a module. Either it is available, or it will be downloaded and loaded.

        Args:
            module_name (str): module name
            module_version (str): module version
            source_link (str): http address of the wheel

        Returns:
            Module: the loaded module
        """
        import os
        import logging
        from gramps.gen.const import USER_PLUGINS
        module = self.check_for(module_name, module_version)
        if module:
            return module

        message = _("Failed to load the required module {module_name} version {module_version}.").format(**locals())
        logging.warning(self.plugin_name + ': ' + message)
        if self.uistate:
            from gramps.gui.dialog import QuestionDialog3
            ok_no_cancel = QuestionDialog3(
                _(self.plugin_name + ' Plugin'),
                _(message),
                _("Don't ask me again"),
                _("Download module"),
                parent=self.uistate.window)
            prompt = ok_no_cancel.run()
            if prompt == True:
                # dont ask me again
                inifile.register(self.plugin_name.lower()+'_warn.missingmodules', "")
                inifile.set(self.plugin_name.lower()+'_warn.missingmodules', "False")
                inifile.save()
                logging.warning(self.plugin_name + ': ' + _('The user chose to deactivate further warnings.'))
                return None
            elif prompt == -1:
                #cancel
                logging.info(self.plugin_name + ': ' + _('The user chose to ignore the warning once.'))
                return None
            elif prompt == False:
                logging.info(self.plugin_name + ': ' + _('The user chose to install the module.'))
                output_path = os.path.join(USER_PLUGINS, self.plugin_name)
                self.load_addon_file(source_link, output_path=output_path, callback=print)
                module = self.check_for(module_name, module_version)
                return module
        return None

    def load_addon_file(self, path, output_path, callback=None):
        """
        Load an module from a particular path (from URL or file system) and extract to output_path.
        """
        from urllib.request import urlopen
        from gramps.gen.plug.utils import urlopen_maybe_no_check_cert
        from io import StringIO, BytesIO
        global Zipfile_bugfix, inifile
        import tarfile
        import os

        download_with_curl = os.name != 'nt'

        if download_with_curl:
            output_filepath = os.path.join(output_path, os.path.basename(path))
            import subprocess
            try:
                exitCode = subprocess.Popen(
                    ['curl', '-L', path, '--output', output_filepath]).wait()
                if exitCode != 0:
                    raise RuntimeError("curl call failed")
            except Exception:
                if callback:
                    callback(_("Unable to open '%s' with curl") % path)
                return False
            path = output_filepath
        if not download_with_curl and (
            path.startswith("http://") or
            path.startswith("https://") or
            path.startswith("ftp://")):
            try:
                fp = urlopen_maybe_no_check_cert(path)
            except RuntimeWarning:
                if callback:
                    callback(_("Unable to open '%s'") % path)
                return False
        else:
            try:
                fp = open(path,'rb')
            except RuntimeWarning:
                if callback:
                    callback(_("Unable to open '%s'") % path)
                if download_with_curl:
                    os.remove(path)
                return False
        try:
            content = fp.read()
            buffer = BytesIO(content)
        except RuntimeWarning:
            if callback:
                callback(_("Error in reading '%s'") % path)
            if download_with_curl:
                os.remove(path)
            return False
        fp.close()
        if download_with_curl:
            os.remove(path)
        # file_obj is either Zipfile or TarFile
        if path.endswith(".zip") or path.endswith(".ZIP"):
            file_obj = Zipfile_bugfix(buffer)
        elif path.endswith(".tar.gz") or path.endswith(".tgz"):
            try:
                file_obj = tarfile.open(None, fileobj=buffer)
            except RuntimeWarning:
                if callback:
                    callback(_("Error: cannot open '%s'") % path)
                return False
        else:
            if callback:
                callback(_("Error: unknown file type: '%s'") % path)
            return False

        try:
            file_obj.extractall(output_path)
        except OSError:
            if callback:
                callback("OSError installing '%s', skipped!" % path)
            file_obj.close()
            return False
        file_obj.close()

        return True

    def cleanup_old_versions(self):
        raise NotImplementedError()