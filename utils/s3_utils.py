import logging

from django.conf import settings

import boto3
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)

def generate_presigned_url(s3_client, client_method, method_parameters, expires_in):
    """
    Generate a presigned url given a client, its method, and arguments

    Parameters:
    ClientMethod (string) – The client method to presign for

    Params (dict) – The parameters normally passed to ClientMethod.

    ExpiresIn (int) – The number of seconds the presigned url is valid for. By default it expires in an hour (3600 seconds)

    HttpMethod (string) – The http method to use on the generated url. By default, the http method is whatever is used in the method’s model.

    Returns:
    The presigned url
    """

    try:
        url = s3_client.generate_presigned_url(
            clientMethod=client_method,
            Params=method_parameters,
            ExpiresIn=expires_in
        )

        logger.info("Got presigned URL: %s", url)
    except ClientError:
        logger.exception("Couldn't get a presigned URL from client method '%s'.", client_method)
        raise
    return url

def rsa_signer(message):
    private_key = serialization.load_pem_private_key(
        settings.AWS_CLOUDFRONT_KEY,
        password=None,
        backend=default_backend()
    )

    signature = private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

    return signature

