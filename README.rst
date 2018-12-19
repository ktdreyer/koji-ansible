koji-ansible
============

Ansible modules to manage Koji resources

koji_tag
--------

The ``koji_tag`` module can create, update, and delete tags within Koji. It can
also manage tag inheritance and the packages list for a tag.

.. code-block:: yaml

    - name: Create a koji tag for the ceph product
      koji_tag:
        name: ceph-3.1-rhel-7
        arches: x86_64
        state: present
        packages:
          kdreyer:
            - ansible
            - ceph
            - ceph-ansible

koji_target
-----------

The ``koji_target`` module can create, update, and delete targets within Koji.

.. code-block:: yaml

    - name: Create a koji build target for Fedora 29
      koji_target:
        name: f29-candidate
        build_tag: f29-build
        dest_tag: f29-updates-candidate
        state: present

koji_cg
-------

The ``koji_cg`` module can grant or revoke access to a `content generator
<https://docs.pagure.org/koji/content_generators/>`_ for a user account.

This user account must already exist in Koji's database. For example, you may
run an authenticated ``koji hello`` command to create the account database
entry.

.. code-block:: yaml

    - name: Grant access to the rcm/debbuild account
      koji_tag:
        koji: mykoji
        name: debian
        user: rcm/debbuild
        state: present

Note, this method tries to call the "grantCGAccess" RPC on every run because
we have no ability to query the current state. See the `listCGs
<https://pagure.io/koji/pull-request/1160>`_ hub RPC in progress.

koji_btype
----------

The ``koji_btype`` module can add new build types. These are typically in
support of `content generators
<https://docs.pagure.org/koji/content_generators/>`_.

(Koji only supports adding new build types, not deleting them.)

.. code-block:: yaml

    - name: Add debian build type to Koji
      koji_btype:
        koji: mykoji
        name: debian
        state: present

koji_archivetype
----------------

The ``koji_archivetype`` module can add new archive types. This allows Koji to
recognize new build archive files, for example ``.deb`` files.  These are
typically in support of `content generators
<https://docs.pagure.org/koji/content_generators/>`_.

(Koji only supports adding new archive types, not deleting them.)

This module uses the new `addArchiveType
<https://pagure.io/koji/pull-request/1149>`_ RPC, which will be available in a
future version of Koji.

.. code-block:: yaml

    - name: Add deb archive type
      koji_archivetype:
        name: deb
        description: Debian packages
        extensions: deb
        state: present

koji_host
---------

The ``koji_host`` module can add new hosts and manage existing hosts.

Koji only supports adding new hosts, not deleting them. Once they're defined,
you can enable or disable the hosts with ``status: enabled`` or ``status:
disabled``.

.. code-block:: yaml

    - name: Add new builder1 host
      koji_host:
        name: builder1.example.com
        arches: [x86_64]
        state: enabled

Koji profiles
-------------

You must tell koji-ansible which Koji client profile to use.

Here is an example of setting a profile explicitly on the task:

.. code-block:: yaml

    - name: Create a koji tag for the ceph product
      koji_tag:
        koji: kojidev
        name: ceph-3.1-rhel-7
        arches: x86_64
        state: present

The ``koji: kojidev`` setting means Ansible will search
``~/.koji/config.d/*.conf`` and ``/etc/koji.conf.d/*.conf`` for the
``[kojidev]`` config section and perform the tag management on that Koji hub
listed there.

To avoid specifying this ``koji:`` argument on every task, you can set the
``KOJI_PROFILE`` environment variable when running ``ansible-playbook``.
koji-ansible will fall back to using ``KOJI_PROFILE`` for the tasks that have
no explicit ``koji:`` argument.

Python paths
------------

These modules import from other files in the ``library`` directory. If you get
``ImportError`` when using these modules,  set the ``PYTHONPATH`` environment
variable to this ``library`` directory.

For example, if you have a ``koji.yml`` playbook that you run with
``ansible-playbook``, it should live alongside this ``library`` directory::

    top
    ├── koji.yml
    └── library

and you should run the playbook like so::

   PYTHONPATH=library ansible-playbook koji.yml


TODO
----

* Ansible-compatible docs
* Unit tests
* A lower-level ``koji_call`` module to make arbitrary RPCs? Like

  .. code-block:: yaml

      koji_call:
        name: createTag
        args:
          name: ceph-3.2-rhel-7
          parent: ...
        failable: true

  This is going to fail a lot of the time (eg createTag for a tag name that
  already exists).

* The long-term goal of this project is to merge into `ansible
  <https://github.com/ansible/ansible/tree/devel/lib/ansible/modules>`_ itself
  so that the modules are built in. To that end, this koji-ansible project is
  licensed under the GPLv3 to match Ansible's license.
