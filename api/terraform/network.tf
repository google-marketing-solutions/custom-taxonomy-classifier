# Copyright 2024 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

## VPC network
##
## Creates a dedicated VPC network and connector for the database
## including required firewall rules.

resource "google_compute_firewall" "allow_internal" {
  name    = "classify-api-network-allow-internal"
  network = google_compute_network.classify_api_network.name

  priority = 65534

  source_ranges = ["10.128.0.0/9"]

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
}

resource "google_compute_network" "classify_api_network" {
  name = "classify-api-network"
}

resource "google_compute_global_address" "private_ip_alloc" {
  name          = "classify-api-db-cluster"
  address_type  = "INTERNAL"
  purpose       = "VPC_PEERING"
  prefix_length = 16
  network       = google_compute_network.classify_api_network.id
}

resource "google_service_networking_connection" "vpc_connection" {
  network                 = google_compute_network.classify_api_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

resource "google_compute_network_peering_routes_config" "peering_routes" {
  peering              = google_service_networking_connection.vpc_connection.peering
  network              = google_compute_network.classify_api_network.name
  import_custom_routes = true
  export_custom_routes = true
}

resource "google_vpc_access_connector" "connector" {
  name          = "classify-api-db-connector"
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.classify_api_network.id
}