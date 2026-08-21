#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.
#
# Modifications Copyright OpenSearch Contributors. See
# GitHub history for details.

"""Compatibility entry point for AOSS client generation."""

from aws_client_codegen.generate_aoss_api import main

if __name__ == "__main__":
    main()
