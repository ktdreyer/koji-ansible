source:
	# TODO: move all this to conf.py:
	#
	# Hack the default behavior from antsibull-docs.
	# Simplify module page titles to be easier to read:
	sed -i 's/^ktdreyer\.koji_ansible\.//' source/*.rst
	# Simplify index page title::
	sed -i 's/^Ktdreyer\.Koji_Ansible/koji-ansible modules/' source/index.rst
	# Remove unhelpful boilerplate:
	sed -i '/Plugin Index/,+1 d' source/index.rst
	sed -i '/These are the plugins in the/d' source/index.rst
	# Remove docs.ansible.com bits from index page:
	sed -i '/\.\. seealso::/d' source/index.rst
	sed -i '/list_of_collections/d' source/index.rst

html: source
	sphinx-build -M html . _build
