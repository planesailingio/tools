get-schema:
	@curl -s -X POST --data-binary @schematic.yaml https://factory.talos.dev/schematics | jq -r '.id'

TALOS_VERSION = "v1.9.1"
download: 
	@VERSION=$$(make --no-print-directory get-schema) && \
	wget https://factory.talos.dev/image/$${VERSION}/${TALOS_VERSION}/vmware-amd64.ova



images:
	@VERSION=$$(make --no-print-directory get-schema) && \
	echo https://factory.talos.dev/image/$${VERSION}/${TALOS_VERSION}/vmware-amd64.ova && \
	echo factory.talos.dev/installer/$${VERSION}:${TALOS_VERSION}