#!powershell
#
# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
# (c) Copyright 2017 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# WANT_JSON
# POWERSHELL_COMMON

$params = Parse-Args $args

$service = Get-Attr $params "service" $FALSE
if ($service -eq $FALSE)
{
    Fail-Json (New-Object psobject) "missing required argument: service"
}

$conf_path = Get-Attr $params "conf_path" $FALSE
If ($conf_path -eq $FALSE)
{
    Fail-Json (New-Object) "missing required argument: conf_path"
}

$cache_path = Get-Attr $params "cache_path" $FALSE
If ($cache_path -eq $FALSE)
{
    Fail-Json (New-Object) "missing required argument: cache_path"
}

$result = New-Object psobject @{
    changed = $FALSE
    url = ""
    svc_dir = ""
    zip = ""
}

# Reading the packager.conf file to get the http server ip & port

$ip_line = Select-String -pattern "url = " -path "$conf_path/packager.conf"
$ip = $ip_line -replace '.*url = ',''


# Downloading the packages file to get the required venv zip file's name
# this will overwrite the packages file if it already exists and we get the
# latest packages file in case the venvs are updated

Invoke-WebRequest "$ip/hyperv_venv/packages" -OutFile "$cache_path/packages"


$entries = Select-String -pattern "$service-.*\.zip" -path `
                "$cache_path/packages" -AllMatches | % { $_.Matches } | `
                % { $_.Value }

# Getting the latest zip file from all the available files if more
# than one entry for the service exists

$result.zip = ($entries | measure -Maximum).Maximum


$result.url = $ip + "hyperv_venv/" + $result.zip

# Returning the venv's name so that it can be used further in the deployment
# as in copying the service conf files
$result.svc_dir = $result.zip -replace '\.zip',''


If (-Not $ip)
{
    Fail-Json (New-Object psobject) "Could not read the ip from conf file"
}

If (-Not $result.zip)
{
    Fail-Json (New-Object psobject) "Could not read the package name"
}

$result.changed = $TRUE

Exit-Json $result;
