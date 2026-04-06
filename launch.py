import os
import json
import tempfile
import requests
from oci.signer import Signer

# 1. Write private key to temp file
key_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
key_file.write(os.environ['OCI_KEY'])
key_file.close()
os.chmod(key_file.name, 0o600)

# 2. Create signer for authentication
signer = Signer(
    tenancy=os.environ['OCI_TENANCY'],
    user=os.environ['OCI_USER'],
    fingerprint=os.environ['OCI_FINGERPRINT'],
    private_key_file_location=key_file.name,
)

# 3. Get latest Ubuntu 22.04 ARM image
region = "ap-chuncheon-1"
base_url = f"https://iaas.{region}.oraclecloud.com/20160918"

resp = requests.get(
    f"{base_url}/images",
    params={
        "compartmentId": os.environ['OCI_TENANCY'],
        "operatingSystem": "Canonical Ubuntu",
        "operatingSystemVersion": "22.04",
        "shape": "VM.Standard.A1.Flex",
        "sortBy": "TIMECREATED",
        "sortOrder": "DESC",
        "limit": 1,
    },
    auth=signer,
)
images = resp.json()
image_id = images[0]["id"]
print(f"Image: {image_id}")

# 4. Launch instance - only required fields, no nulls
body = {
    "availabilityDomain": "QIZn:AP-CHUNCHEON-1-AD-1",
    "compartmentId": os.environ['OCI_TENANCY'],
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
        "subnetId": os.environ['OCI_SUBNET']
    },
    "metadata": {
        "ssh_authorized_keys": os.environ['OCI_SSH_KEY'].strip()
    }
}

print(f"Request:\n{json.dumps(body, indent=2)}")

resp = requests.post(
    f"{base_url}/instances",
    json=body,
    auth=signer,
)

print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

github_output = os.environ.get('GITHUB_OUTPUT', '')

if resp.status_code == 200:
    data = resp.json()
    print(f"SUCCESS! Instance OCID: {data['id']}")
    if github_output:
        with open(github_output, 'a') as f:
            f.write("success=true\n")
else:
    print(f"FAILED")
    if github_output:
        with open(github_output, 'a') as f:
            f.write("success=false\n")

os.unlink(key_file.name)
