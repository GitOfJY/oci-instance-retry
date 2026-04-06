import os
import json
import tempfile
import oci

# 1. Private key
key_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
key_file.write(os.environ['OCI_KEY'])
key_file.close()
os.chmod(key_file.name, 0o600)

config = {
    "user": os.environ['OCI_USER'],
    "fingerprint": os.environ['OCI_FINGERPRINT'],
    "tenancy": os.environ['OCI_TENANCY'],
    "region": "ap-chuncheon-1",
    "key_file": key_file.name,
}

identity = oci.identity.IdentityClient(config)
compute = oci.core.ComputeClient(config)
network = oci.core.VirtualNetworkClient(config)

tenancy_id = os.environ['OCI_TENANCY']
subnet_id = os.environ['OCI_SUBNET']

# 2. Verify subnet
print(f"Subnet OCID: {subnet_id}")
print(f"Subnet OCID length: {len(subnet_id)}")
try:
    subnet = network.get_subnet(subnet_id).data
    print(f"Subnet name: {subnet.display_name}")
    print(f"Subnet state: {subnet.lifecycle_state}")
    print(f"Subnet is public: {not subnet.prohibit_public_ip_on_vnic}")
    print(f"VCN ID: {subnet.vcn_id}")
except Exception as e:
    print(f"ERROR getting subnet: {e}")
    exit(1)

# 3. Get availability domain
ads = identity.list_availability_domains(tenancy_id).data
ad_name = ads[0].name
print(f"Availability domain: {ad_name}")

# 4. Get image
images = compute.list_images(
    compartment_id=tenancy_id,
    operating_system="Canonical Ubuntu",
    operating_system_version="22.04",
    shape="VM.Standard.A1.Flex",
    sort_by="TIMECREATED",
    sort_order="DESC",
    limit=1,
).data
image_id = images[0].id
print(f"Image: {image_id}")

# 5. SSH key
ssh_key = os.environ['OCI_SSH_KEY'].strip()
print(f"SSH key length: {len(ssh_key)}")
print(f"SSH key first 40 chars: {ssh_key[:40]}")
print(f"SSH key last 20 chars: {ssh_key[-20:]}")

# 6. Launch with REST API (no nulls)
from oci.signer import Signer

signer = Signer(
    tenancy=tenancy_id,
    user=os.environ['OCI_USER'],
    fingerprint=os.environ['OCI_FINGERPRINT'],
    private_key_file_location=key_file.name,
)

import requests as req

body = {
    "availabilityDomain": ad_name,
    "compartmentId": tenancy_id,
    "displayName": "shopai-server",
    "shape": "VM.Standard.A1.Flex",
    "shapeConfig": {
        "ocpus": 4.0,
        "memoryInGbs": 24.0
    },
    "sourceDetails": {
        "sourceType": "image",
        "imageId": image_id
    },
    "createVnicDetails": {
        "subnetId": subnet_id
    },
    "metadata": {
        "ssh_authorized_keys": ssh_key
    }
}

body_str = json.dumps(body)
print(f"\nRequest body length: {len(body_str)}")

resp = req.post(
    f"https://iaas.ap-chuncheon-1.oraclecloud.com/20160918/instances",
    data=body_str,
    headers={"Content-Type": "application/json"},
    auth=signer,
)

print(f"\nStatus: {resp.status_code}")
result = resp.json()
print(f"Response: {json.dumps(result, indent=2)[:500]}")

github_output = os.environ.get('GITHUB_OUTPUT', '')
if resp.status_code == 200:
    print(f"\nSUCCESS! Instance OCID: {result['id']}")
    if github_output:
        with open(github_output, 'a') as f:
            f.write("success=true\n")
else:
    print(f"\nFAILED")
    if github_output:
        with open(github_output, 'a') as f:
            f.write("success=false\n")

os.unlink(key_file.name)
