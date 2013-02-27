%define ver 1

Name:		opencenter-client
Version:	0.1.0
Release:	%{ver}%{?dist}
Summary:	Client library for OpenCenter API

Group:		System
License:	None
URL:		https://github.com/rcbops/opencenter-client
Source0:	opencenter-client-%{version}.tgz
Source1:	local.conf

BuildRequires:  python-setuptools
Requires:	python-requests
Requires:	python >= 2.6

BuildArch: noarch


%description
Client library for OpenCenter API

%prep
%setup -q -n %{name}-%{version}

%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build

%install
mkdir -p $RPM_BUILD_ROOT/etc
mkdir -p $RPM_BUILD_ROOT/usr/bin
install -m 644 $RPM_SOURCE_DIR/local.conf $RPM_BUILD_ROOT/etc/local.conf
%{__python} setup.py install --skip-build --root $RPM_BUILD_ROOT


%files
%config(noreplace) /etc/local.conf
%defattr(-,root,root)
%{python_sitelib}/opencenter_client*
%{python_sitelib}/opencenterclient*
/usr/bin/r2
/usr/bin/opencenter
%doc

%clean
rm -rf $RPM_BUILD_ROOT

%post

%changelog
* Mon Oct 2 2012 Joseph W. Breu (joseph.breu@rackspace.com) - 1.0
- Initial build
