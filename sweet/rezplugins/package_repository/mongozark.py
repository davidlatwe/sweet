
from rez.package_repository import PackageRepository
from rez.package_resources import (
    PackageFamilyResource,
    VariantResourceHelper,
    PackageResourceHelper,
    package_pod_schema,
    package_release_keys,
    package_build_only_keys,
)
from rez.exceptions import (
    PackageRepositoryError,
    PackageMetadataError,
    RezSystemError,
)
from rez.utils.formatting import is_valid_package_name
from rez.utils.resources import cached_property
from rez.utils.logging_ import print_warning
from rez.config import config
from rez.backport.lru_cache import lru_cache
from rez.vendor.six import six

from rez.utils.sourcecode import SourceCode
from rez.vendor.version.version import Version
from rez.utils.formatting import PackageRequest

import os
import time
import socket
import getpass
import datetime

from pymongo import MongoClient, errors as pymongo_err

basestring = six.string_types[0]


class PackageDefinitionFileMissing(PackageMetadataError):
    pass


def package_family_document(name, date):
    return {
        "type": "family",
        "_id": name,     # family `name` should be unique
        "date": date,
    }


def package_document(name, date, version, package_dict):
    return {
        "type": "package",
        "family": name,
        "version": version,
        "package": package_dict,
        "date": date,
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
    }


def _encode(obj):

    if isinstance(obj, list):
        return [
            _encode(element) for element in obj
        ]

    if isinstance(obj, SourceCode):
        # Reference: SourceCode.__getstate__
        return {
            "::rez:sourcecode::": dict(
                source=obj.source,
                filepath=obj.filepath,
                funcname=obj.funcname,
                eval_as_function=obj.eval_as_function,
                decorators=obj.decorators,
            )
        }

    if isinstance(obj, Version):
        return {
            "::rez:version::": dict(
                version=str(obj),
            )
        }

    if isinstance(obj, PackageRequest):
        # No need to decode it back
        return str(obj)

    return obj


def package_to_dict(package):
    return {
        k: _encode(v)
        for k, v in package.items()
        if v is not None
    }


def _decode(obj):

    if not isinstance(obj, dict):
        return obj

    if "::rez:sourcecode::" in obj:
        value = obj["::rez:sourcecode::"]

        source_code = SourceCode()
        # Reference: SourceCode.__setstate__
        source_code.source = value["source"]
        source_code.filepath = value["filepath"]
        source_code.funcname = value["funcname"]
        source_code.eval_as_function = value["eval_as_function"]
        source_code.decorators = value["decorators"]

        return source_code

    if "::rez:version::" in obj:
        value = obj["::rez:version::"]

        return Version(value["version"])

    return obj


def package_from_dict(package):
    return {
        k: _decode(v)
        for k, v in package.items()
        if v is not None
    }


# ------------------------------------------------------------------------------
# resources
# ------------------------------------------------------------------------------


class MongozarkPackageFamilyResource(PackageFamilyResource):
    key = "mongozark.family"
    repository_type = "mongozark"

    def _uri(self):
        return "%s@%s" % (self.name, self.location)

    def get_last_release_time(self):
        document = self._repository.collection.find_one(
            {"type": "family", "_id": self.name},
            projection={"date": True},
        )

        if document is None or "date" not in document:
            return 0
        else:
            return time.mktime(document["date"].timetuple())

    def iter_packages(self):
        for document in self._repository.collection.find(
            {"type": "package", "family": self.name},
            projection={"version": True},
            sort=[("version", -1)],  # latest first
        ):

            package = self._repository.get_resource(
                MongozarkPackageResource.key,
                location=self.location,
                name=self.name,
                version=document["version"])

            yield package


class MongozarkPackageResource(PackageResourceHelper):
    key = "mongozark.package"
    variant_key = "mongozark.variant"
    repository_type = "mongozark"
    schema = package_pod_schema

    def _uri(self):
        # (NOTE) Prefix uri with filesystem root path so that we can still
        #   have path like "{root}/sub-dir" in package attribute and able
        #   to find resources that can only be stored in filesystem. For
        #   example, profile icon that can be shown on Allzpark.
        #
        #   The `filesystem_root` is an attribute that can be saved in a
        #   package.py file and able to be written into database.
        #
        #   Currently, it can be set like this:
        #   ```
        #   # in package.py
        #   filesystem_root = os.getcwd()
        #   ```
        #   Also, this might be hacky to get package attribute from `_data`,
        #   please let me know if there is a better way.
        #
        source = self._data.get("filesystem_root", "")
        uri = "~mongozark@%s" % self.location
        return os.path.join(source, uri)

    @property
    def base(self):
        return self._data.get("filesystem_root")

    @cached_property
    def parent(self):
        family = self._repository.get_resource(
            MongozarkPackageFamilyResource.key,
            location=self.location,
            name=self.name)
        return family

    def state_handle(self):
        # Not applicable to mongodb repository type
        #
        # This is used for resolve caching. For example, in the 'filesystem'
        # repository type, the 'state' is the last modified date of the file
        # associated with the variant (perhaps a package.py). Which don't fit
        # for repository that backed with database.

        return None

    def iter_variants(self):
        indexes = [None]  # No variant needed/allowed in mongozark

        for index in indexes:
            variant = self._repository.get_resource(
                self.variant_key,
                location=self.location,
                name=self.name,
                version=self.get("version"),
                index=index)

            yield variant

    def _load(self):
        document = self._repository.collection.find_one(
            {
                "type": "package",
                "family": self.name,
                "version": self.get("version"),
            },
            projection={"package": True}
        )

        if document is None:
            raise PackageDefinitionFileMissing(
                "Missing package definition file: %r" % self)

        return package_from_dict(document["package"])


class MongozarkVariantResource(VariantResourceHelper):
    key = "mongozark.variant"
    repository_type = "mongozark"

    @cached_property
    def parent(self):
        package = self._repository.get_resource(
            MongozarkPackageResource.key,
            location=self.location,
            name=self.name,
            version=self.get("version"))
        return package

    @cached_property
    def root(self):
        return self.parent._data.get("filesystem_root")


def is_mongodb_reachable(client):
    try:
        client.server_info()
    except pymongo_err.ServerSelectionTimeoutError as e:
        print_warning(e)
        return False
    else:
        return True


class MongozarkPackageRepository(PackageRepository):
    """
    """

    @classmethod
    def name(cls):
        return "mongozark"

    def __init__(self, location, resource_pool):
        """Create a mongo package repository.

        Args:
         location (str): Path containing the package repository.

        """
        database, uri_key = location.split(".", 2)
        collection = uri_key

        settings = config.plugins.package_repository.mongozark
        uri = getattr(settings.uri, uri_key, None)

        if uri is None:
            raise PackageRepositoryError(
                "URI key '%s' not found in "
                "'config.plugins.package_repository.mongozark.uri'." % uri_key)

        select_timeout = settings.mongodb.select_timeout
        client = MongoClient(uri, serverSelectionTimeoutMS=select_timeout)
        is_connected = is_mongodb_reachable(client)

        db = client[database]
        collection = db[collection]

        self.database_uri = uri
        self.is_connected = is_connected
        self.collection = collection

        super(MongozarkPackageRepository, self).__init__(location,
                                                         resource_pool)

        self.register_resource(MongozarkPackageFamilyResource)
        self.register_resource(MongozarkVariantResource)
        self.register_resource(MongozarkPackageResource)

        self.get_families = lru_cache(maxsize=None)(self._get_families)
        self.get_family = lru_cache(maxsize=None)(self._get_family)
        self.get_packages = lru_cache(maxsize=None)(self._get_packages)
        self.get_variants = lru_cache(maxsize=None)(self._get_variants)

    def _uid(self):
        return self.name(), self.location

    def get_package_family(self, name):
        if not self.is_connected:
            return
        return self.get_family(name)

    def iter_package_families(self):
        if not self.is_connected:
            return
        for family in self.get_families():
            yield family

    def iter_packages(self, package_family_resource):
        if not self.is_connected:
            return
        for package in self.get_packages(package_family_resource):
            yield package

    def iter_variants(self, package_resource):
        if not self.is_connected:
            return
        for variant in self.get_variants(package_resource):
            yield variant

    def get_parent_package_family(self, package_resource):
        return package_resource.parent

    def get_parent_package(self, variant_resource):
        return variant_resource.parent

    def get_variant_state_handle(self, variant_resource):
        # Not applicable to mongodb repository type, leave it as-is.
        return None

    def get_last_release_time(self, package_family_resource):
        return package_family_resource.get_last_release_time()

    def install_variant(self, variant_resource, dry_run=False, overrides=None):
        if not self.is_connected:
            raise PackageRepositoryError("%s is not connected to [%s]." %
                                         (self.location, self.database_uri))

        overrides = overrides or {}

        # Name and version overrides are a special case - they change the
        # destination variant to be created/replaced.
        #
        variant_name = variant_resource.name
        variant_version = variant_resource.version

        if "name" in overrides:
            variant_name = overrides["name"]
            if variant_name is self.remove:
                raise PackageRepositoryError(
                    "Cannot remove package attribute 'name'")

        if "version" in overrides:
            ver = overrides["version"]
            if ver is self.remove:
                raise PackageRepositoryError(
                    "Cannot remove package attribute 'version'")

            if isinstance(ver, basestring):
                ver = Version(ver)
                overrides = overrides.copy()
                overrides["version"] = ver

            variant_version = ver

        # cannot install over one's self, just return existing variant
        if variant_resource._repository is self and \
                variant_name == variant_resource.name and \
                variant_version == variant_resource.version:
            return variant_resource

        # install the variant
        variant = self._create_variant(variant_resource,
                                       dry_run=dry_run,
                                       overrides=overrides)
        return variant

    def clear_caches(self):
        super(MongozarkPackageRepository, self).clear_caches()
        self.get_families.cache_clear()
        self.get_family.cache_clear()
        self.get_packages.cache_clear()

    def get_package_payload_path(self, package_name, package_version=None):
        # (NOTE) We wouldn't need this,
        #   but the local build process need a place to write
        #   out `build.rxt` file, so we set the path to the
        #   build dir.
        path = os.path.join("build", ".install")
        return path

    def _get_families(self):
        families = []

        for name in self.collection.distinct("_id", {"type": "family"}):
            family = self.get_resource(
                MongozarkPackageFamilyResource.key,
                location=self.location,
                name=name)

            families.append(family)

        return families

    def _get_family(self, name):
        is_valid_package_name(name, raise_error=True)

        document = self.collection.find_one({"type": "family", "_id": name},
                                            projection={"_id": True})
        if document is not None:

            family = self.get_resource(
                MongozarkPackageFamilyResource.key,
                location=self.location,
                name=name
            )

            return family

    def _get_packages(self, package_family_resource):
        return [x for x in package_family_resource.iter_packages()]

    def _get_variants(self, package_resource):
        return [x for x in package_resource.iter_variants()]

    def _create_variant(self, variant, dry_run=False, overrides=None):
        # special case overrides
        variant_name = overrides.get("name") or variant.name
        variant_version = overrides.get("version") or variant.version

        overrides = (overrides or {}).copy()
        overrides.pop("name", None)
        overrides.pop("version", None)

        # Need to treat 'config' as special case. In validated data, this is
        # converted to a Config object. We need it as the raw dict that you'd
        # see in a package.py.
        #
        def _get_package_data(pkg):
            data = pkg.validated_data()
            if hasattr(pkg, "_data"):
                raw_data = pkg._data
            else:
                raw_data = pkg.resource._data

            raw_config_data = raw_data.get("config")
            data.pop("config", None)

            if raw_config_data:
                data["config"] = raw_config_data

            return data

        def _remove_build_keys(obj):
            for key in package_build_only_keys:
                obj.pop(key, None)

        package_data = _get_package_data(variant.parent)
        package_data.pop("variants", None)
        package_data["name"] = variant_name
        if variant_version:
            package_data["version"] = variant_version

        _remove_build_keys(package_data)

        installed_variant_index = None

        if dry_run:
            return None

        # a little data massaging is needed
        package_data.pop("base", None)

        # Apply overrides
        for key, value in overrides.items():
            if value is self.remove:
                package_data.pop(key, None)
            else:
                package_data[key] = value

        # timestamp defaults to now if not specified
        if not package_data.get("timestamp"):
            package_data["timestamp"] = int(time.time())

        # format version is always set
        package_data["format_version"] = 2  # Late binding functions added

        # Stop if package is unversioned and config does not allow that
        if (not package_data["version"]
                and not config.allow_unversioned_packages):
            raise PackageMetadataError("Unversioned package is not allowed.")

        # Upsert to database
        date = datetime.datetime.now()
        family_name = package_data["name"]
        version_string = str(package_data["version"])

        document = package_family_document(family_name, date)
        filter_ = {
            "type": "family",
            "_id": family_name,
        }
        self.collection.update_one(filter_, {"$set": document}, upsert=True)

        document = package_document(family_name,
                                    date,
                                    version_string,
                                    package_to_dict(package_data))
        filter_ = {
            "type": "package",
            "family": family_name,
            "version": version_string,
        }
        self.collection.update_one(filter_, {"$set": document}, upsert=True)

        # load new variant
        new_variant = None
        self.clear_caches()
        family = self.get_package_family(variant_name)

        if family:
            for package in self.iter_packages(family):
                if package.version == variant_version:
                    for variant_ in self.iter_variants(package):
                        if variant_.index == installed_variant_index:
                            new_variant = variant_
                            break
                elif new_variant:
                    break

        if not new_variant:
            raise RezSystemError("Internal failure - expected installed variant")

        return new_variant


def register_plugin():
    return MongozarkPackageRepository
