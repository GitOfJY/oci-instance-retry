import oci
import os
import tempfile

# 1. Write private key to temp file
key_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
key_file.write(os.environ['OCI_KEY'])
key_file.close()
os.chmod(key_file.name, 0o600)

# 2. Build config
config = {
    "user": os.environ['OCI_USER'],
    "fingerprint": os.environ['OCI_FINGERPRINT'],
    "tenancy": os.environ['OCI_TENANCY'],
    "region": "ap-chuncheon-1",
    "key_file": key_file.name,
}

# 3. Create compute client
compute = oci.core.ComputeClient(config)

# 4. Get latest Ubuntu 22.04 ARM image
images = compute.list_images(
    compartment_id=os.environ['OCI_TENANCY'],
    operating_system="Canonical Ubuntu",
    operating_system_version="22.04",
    shape="VM.Standard.A1.Flex",
    sort_by="TIMECREATED",
    sort_order="DESC",
    limit=1,
).data

if not images:
    print("ERROR: No Ubuntu 22.04 ARM image found")
    exit(1)

image_id = images[0].id
print(f"Image found: {image_id}")

# 5. Launch instance
try:
    result = compute.launch_instance(
        oci.core.models.LaunchInstanceDetails(
            availability_domain="QIZn:AP-CHUNCHEON-1-AD-1",
            compartment_id=os.environ['OCI_TENANCY'],
            display_name="shopai-server",
            shape="VM.Standard.A1.Flex",
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=4.0,
                memory_in_gbs=24.0,
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                image_id=image_id,
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=os.environ['OCI_SUBNET'],
                assign_public_ip=True,
            ),
            metadata={
                "ssh_authorized_keys": os.environ['OCI_SSH_KEY'].strip(),
            },
        )
    )
    print(f"SUCCESS! Instance OCID: {result.data.id}")
    print(f"Lifecycle state: {result.data.lifecycle_state}")

    # Write success to GitHub Actions output
    github_output = os.environ.get('GITHUB_OUTPUT', '')
    if github_output:
        with open(github_output, 'a') as f:
            f.write("success=true\n")

except oci.exceptions.ServiceError as e:
    print(f"FAILED: [{e.code}] {e.message}")

    github_output = os.environ.get('GITHUB_OUTPUT', '')
    if github_output:
        with open(github_output, 'a') as f:
            f.write("success=false\n")

finally:
    os.unlink(key_file.name)
