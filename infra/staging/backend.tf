# Remote state. Actual bucket/key/region come from backend.hcl (git-ignored).
# Bootstrap: cp backend.hcl.example backend.hcl && edit as needed, then run
# infra/setup.sh staging

terraform {
  backend "s3" {}
}
