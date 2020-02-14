koji-ansible
============

.. image:: https://travis-ci.org/ktdreyer/koji-ansible.svg?branch=master
             :target: https://travis-ci.org/ktdreyer/koji-ansible

.. image:: https://coveralls.io/repos/github/ktdreyer/koji-ansible/badge.svg
             :target: https://coveralls.io/github/ktdreyer/koji-ansible


Ansible modules to manage `Koji <https://pagure.io/koji>`_ resources.

This is not about installing Koji. Instead, it is a way to declaratively
define things within Koji, where you might normally use the koji CLI.

koji_tag
--------

The ``koji_tag`` module can create, update, and delete tags within Koji. It can
also manage tag inheritance, packages list and group list for a tag.

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
	groups:
	  srpm-build:
	    - rpm-build
	    - fedpkg

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

koji_external_repo
------------------

The ``koji_external_repo`` module can create, update, and delete `external
repositories <https://docs.pagure.org/koji/external_repo_server_bootstrap/>`_
within Koji.

.. code-block:: yaml

    - name: Create an external repo for CentOS "CR"
      koji_external_repo:
        name: centos7-cr
        url: http://mirror.centos.org/centos/7/cr/$arch/
        state: present

You can then configure these repositories (and their priorities) on each of
your Koji tags with the ``external_repos`` parameter to the ``koji_tag``
module.

koji_cg
-------

The ``koji_cg`` module can grant or revoke access to a `content generator
<https://docs.pagure.org/koji/content_generators/>`_ for a user account.

This user account must already exist in Koji's database. For example, you may
run an authenticated ``koji hello`` command to create the account database
entry.

.. code-block:: yaml

    - name: Grant access to the rcm/debbuild account
      koji_cg:
        koji: mykoji
        name: debian
        user: rcm/debbuild
        state: present

Your Koji Hub must be version 1.19 or newer in order to use the new
`listCGs <https://pagure.io/koji/pull-request/1160>`_ RPC.

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

Your Koji Hub must be version 1.20 or newer in order to use the new
`addArchiveType <https://pagure.io/koji/pull-request/1149>`_ RPC.

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
you can enable or disable the hosts with ``state: enabled`` or ``state:
disabled``.

.. code-block:: yaml

    - name: Add new builder1 host
      koji_host:
        name: builder1.example.com
        arches: [x86_64]
        state: enabled
        channels:
          - default
          - createrepo

If you specify channels that do not yet exist, Ansible will create them. For
example, if you are setting up a new builder host for `OSBS
<https://osbs.readthedocs.io>`_, you can specify ``container`` in the list of
channels, and Ansible will automatically create that new "container" channel
when it configures the host.

koji_user
---------

The ``koji_user`` module can add new users and manage existing users and
permissions.

Koji only supports adding new users, not deleting them. Once they're defined,
you can enable or disable the users with ``state: enabled`` or ``state:
disabled``.

.. code-block:: yaml

    - name: Add new kdreyer user
      koji_user:
        name: kdreyer
        state: enabled
        permissions: [admin]

koji_tag_inheritance
--------------------

The ``koji_tag`` module (above) is all-or-nothing when it comes to managing
tag inheritance. When you set inheritance with ``koji_tag``, the module will
delete any inheritance relationships that are not defined there.

In some cases you may want to declare *some* inheritance relationships within
Ansible without clobbering other existing inheritance relationships. For
example, `MBS <https://fedoraproject.org/wiki/Changes/ModuleBuildService>`_
will dynamically manage some inheritance relationships of tags, and you do not
want Ansible to fight MBS.

To declare inheritance relationships with finer granularity, you may use the
``koji_tag_inheritance`` module.

.. code-block:: yaml

    - name: set devtoolset-7 as a parent of ceph nautilus
      koji_tag_inheritance:
        parent_tag: sclo7-devtoolset-7-rh-release
        child_tag: storage7-ceph-nautilus-el7-build
        priority: 25

This will only mange that single parent-child relationship between the two
tags, and it will not delete any other inheritance relationships.

koji_call
---------

The ``koji_call`` module allows you to send raw RPCs to the Koji hub. This
exposes the entire Koji API to you directly.

Why would you use this module instead of the higher level modules like
``koji_tag``, ``koji_target``, etc? This ``koji_call`` module has two main
uses-cases:

1. You may want to do something that the higher level modules do not yet
   support. It can be easier to use this module to quickly prototype out your
   ideas for what actions you need, and then write the Python code to do it in
   a better way later. If you find that you need to use koji_call to achieve
   functionality that is not yet present in the other koji-ansible modules,
   please file a Feature Request issue in `GitHub
   <https://github.com/ktdreyer/koji-ansible/issues>`_ with your use case.
2. You want to write some tests that verify Koji's data at a very low level.
   For example, you may want to write an integration test to verify that
   you've set up your Koji configuration in the way you expect.

Note that this module will always report "changed: true" every time, because
it simply sends the RPC to the Koji Hub on every ansible run.  This module
cannot understand if your chosen RPC actually "changes" anything.

.. code-block:: yaml

    - name: make a raw API call:
      koji_call:
        name: getTag
        args: [f29-build]
      register: call_result

    - debug:
        var: call_result.data

This will print the tag information for the `Fedora 29 -build tag
<https://koji.fedoraproject.org/koji/taginfo?tagID=3428>`_. It is similar
to running ``koji taginfo f29-build`` on the command-line.

Koji profiles
-------------

You must tell koji-ansible which `Koji client profile
<https://docs.pagure.org/koji/profiles/>`_ to use.

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
no explicit ``koji:`` argument::

   KOJI_PROFILE=kojidev ansible-playbook -v my-koji-playbook.yaml


Installing from Ansible Galaxy
------------------------------

We distribute koji-ansible through the `Ansible Galaxy
<https://galaxy.ansible.com/ktdreyer/koji_ansible>`_.

If you are using Ansible 2.9 or greater, you can `install
<https://docs.ansible.com/ansible/latest/user_guide/collections_using.html>`_
koji-ansible like so::

  ansible-galaxy collection install ktdreyer.koji_ansible:<identifier>

Where *<identifier>* is a specific Git reference. Please see the `Ansible
Galaxy UI <https://galaxy.ansible.com/ktdreyer/koji_ansible>`_.

Please note that you cannot install the "latest" Git snapshot automatically
without specifying the version identifier explicitly. The problem is that the
``ansible-galaxy`` client hides these versions when it picks the "latest" one
to install. This issue is tracked in
https://github.com/ansible/ansible/issues/64905 .

Using this Ansible Galaxy Collection inside a role
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is an example of a simple playbook and role that uses this collection.
``playbook.yml`` calls one role named ``my-koji-project``::

    top
    ├── playbook.yml
    └── roles
        └── my-koji-project
            ├── collections
            │   └── requirements.yml
            ├── meta
            │   └── main.yml
            └── tasks
                └── main.yml

The ``playbook.yml`` file is a small playbook that simply loads our role::

    - name: Test a role that uses koji-ansible
      hosts: localhost
      gather_facts: false
      roles:
       - my-koji-project

The ``roles/my-koji-project/collections/requirements.yml`` file should require
this collection (and a specific version, as described above)::

    collections:
    - name: ktdreyer.koji_ansible
      version: 0.0.0-git.222+7fb2d32f

The ``roles/my-koji-project/meta/main.yml`` file tells Ansible to load any
custom modules in this role from the ``ktdreyer.koji_ansible`` collection
namespace::

    collections:
    - ktdreyer.koji_ansible

Lastly you can add your role's tasks as usual to ``roles/my-koji-project/tasks/main.yml``::

    - name: create the "my-product-1.0" tag
      koji_tag:
        name: my-product-1.0


Running from a Git clone
------------------------

Instead of using the Ansible Collection tarball, you can use this project
directly from a Git clone. This is useful when hacking on the code.

These modules import ``common_koji`` from the ``module_utils`` directory.

One easy way to arrange your Ansible files is to symlink the ``library`` and
``module_utils`` directories into the directory with your playbook.

For example, if you have a ``koji.yml`` playbook that you run with
``ansible-playbook``, it should live alongside these ``library`` and
``module_utils`` directories::

    top
    ├── koji.yml
    ├── module_utils
    └── library

and you should run the playbook like so::

   ansible-playbook koji.yml


Investigating changes that happened outside Ansible
---------------------------------------------------

Koji tracks a history of everything in its database. You can view this history
with the ``koji list-history`` and ``koji list-tag-history`` sub-commands.

For example, let's say that you wake up one morning to find that your Ansible
playbook for your tags no longer matches up with what is configured live in
Koji. Did someone else on your team make a change with the CLI without editing
the playbook or notifying you? Who did it, and when? Use ``koji list-history
--tag=my-tag`` to see the entire list of changes for your tag in the database.
After a friendly chat with the person who made the change, you can work
together to record the change within your Ansible playbook so your sources of
truth remain consistent.


Generating a playbook from a live Koji instance
-----------------------------------------------

Do you have a Koji hub that has many tags, targets, and other settings that
were crafted by hand over the years? You can use the
``./utils/generate-playbook`` script to query your Koji hub and write an
Ansible playbook that describes some or all of the tags. You can then store
this YAML in Git. Other things beyond tags and targets (like content
generators or users) are not yet supported.

This ``generate-playbook`` utility's output may not be the most elegant way to
manage your Koji tags. There will be lots of repetition, because it will not
use any Ansible variables, etc. The purpose of this utility is simply to help
you get up and running quickly with koji-ansible.


TODO
----

* Unit tests
