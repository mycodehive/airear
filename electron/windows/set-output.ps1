param([string]$Endpoint, [switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("870af99c-171d-4f9e-af0d-e63df40c2bc9")] class PolicyConfigClient {}
[ComImport, Guid("f8679f50-850a-41cf-9c72-430f290290c8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IPolicyConfig {
 void GetMixFormat(); void GetDeviceFormat(); void ResetDeviceFormat(); void SetDeviceFormat();
 void GetProcessingPeriod(); void SetProcessingPeriod(); void GetShareMode(); void SetShareMode();
 void GetPropertyValue(); void SetPropertyValue();
 [PreserveSig] int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string id, int role);
 void SetEndpointVisibility();
}
public static class AirEarOutput {
 public static void Set(string id) {
  var policy = (IPolicyConfig)new PolicyConfigClient();
  try { for (int role=0; role<3; role++) Marshal.ThrowExceptionForHR(policy.SetDefaultEndpoint(id, role)); }
  finally { Marshal.ReleaseComObject(policy); }
 }
}
'@
if ($ValidateOnly) { exit 0 }
if ([string]::IsNullOrWhiteSpace($Endpoint)) { throw 'A render endpoint ID is required.' }
[AirEarOutput]::Set($Endpoint)
