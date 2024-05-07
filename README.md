# intermediate-ca-bundle

This is a collection of intermediate Certificate Authority (CA) certificates.
This is useful when connecting to servers with incomplete certificate chains, which is a problem for automated tools:

```
$ curl -I 'https://eatcs.org'  # Doesn't work!
curl: (60) SSL certificate problem: unable to get local issuer certificate
More details here: https://curl.se/docs/sslcerts.html

curl failed to verify the legitimacy of the server and therefore could not
establish a secure connection to it. To learn more about this situation and
how to fix it, please visit the web page mentioned above.
[$? = 60]
```

This project provides a [weekly-updated `intermediate_certs.pem` file](https://raw.githubusercontent.com/BenWiederhake/intermediate-ca-bundle/blob/intermediate_certs.pem), which you can use like this:

```
$ curl --proto '=https' --tlsv1.2 -sSf -O 'https://raw.githubusercontent.com/BenWiederhake/intermediate-ca-bundle/blob/intermediate_certs.pem'  # Download

$ cat /etc/ssl/certs/ca-certificates.crt intermediate_certs.pem > combined.pem  # Combine with your system root CA certs

$ curl --cacert combined.pem -I 'https://eatcs.org'  # Works nicely :)
HTTP/1.1 200 OK
Date: Sun, 22 Oct 2023 12:32:32 GMT
Server: Apache/2.4.7 (Ubuntu)
X-Powered-By: PHP/5.5.9-1ubuntu4.29
Set-Cookie: a3e0d243e21c833c2e18766e1ee5c543=dlr966mq8vj6adlnidl49aqdo5; path=/; secure
P3P: CP="NOI ADM DEV PSAi COM NAV OUR OTRo STP IND DEM"
Expires: Mon, 1 Jan 2001 00:00:00 GMT
Last-Modified: Sun, 22 Oct 2023 12:32:32 GMT
Cache-Control: post-check=0, pre-check=0
Pragma: no-cache
Content-Type: text/html; charset=utf-8
```

Note that the root CA certificates are still necessary because not all servers use an intermediate certificate (perhaps one that is not included by Mozilla, or none at all).

If you're here because you saw `CowBirdTacitFlower` appear in your logs, please write me an e-mail or [open an issue](https://github.com/BenWiederhake/intermediate-ca-bundle/issues/new).

## Table of Contents

- [How TLS should work](#how-tls-should-work)
- [Where certs are stored](#where-certs-are-stored)
- [The problem](#the-problem)
- [The solution in this project](#the-solution-in-this-project)
- [See also](#see-also)
- [Installation](#installation)
- [Usage](#usage)
- [Formats, and ease of access](#formats-and-ease-of-access)
- [TODOs](#todos)
- [NOTDOs](#notdos)
- [Contribute](#contribute)

## How TLS should work

The process of establishing a secure TLS connection (https, ftps, DoH, etc.) involves at least one side being able to cryptographically prove their identity; usually the server. This is usually done through a certificate *chain*. Here's a simplified summary:
- A *root* CA certificate simply says "The CA with name <ABCD> has the public key <1234>."
  The idea is that there are only relatively [few](https://packages.debian.org/stable/all/ca-certificates/filelist) root CAs in existence, which can be reasonably audited manually.
- A *server* certificate essentially says "The server at example.com has the public key <2345>. I am certificate authority <3456>, and here's my cryptographic signature to prove it."
  The idea is that server certificates are short-lived, easy to replace and update. The certificate authority might be a root CA, but that causes some bottlenecks and other issues. Hence the need for another, intermediate step:
- An *intermediate* CA certificate basically says "The CA with name <EFGH> has the public key <4567>. I am certificate authority <5678>, and here's my cryptographic signature to prove it.", along with a cryptographic signature of a *higher-level* CA.
  The idea is that *intermediate* certificates are much easier to replace than root CA certificates, while at the same time being much longer lived than server certificates.

Of course, this glosses over a lot of details, edge cases, restrictions, and other features.

This gist is: Your computer knows a handful of root CAs, and what their public keys are. Together with a certificate chain (i.e. zero or more intermediate CA certificates plus one server certificate), you can then verify each step of the chain, and thus verify that the server you're talking to really is supposed to have the public key it has.

## Where certs are stored

Of course, this only works if you have all the certificates for this chain:
- The root CA must be part of your operating system, or browser, or something that you already have before making the connection. This is unavoidable, since trust has to start *somewhere*. This means that vendors somehow need to verify the identity of each CA, and roll out updates whenever something changes. This is the reason why CA certificates necessarily are long-lived, and hard to replace.
- The server certificates cannot possibly be already on your system. Just attempting to list several billion domain names requires gigabytes of data. Hence, server certificates are always delivered while connecting. This makes them easy to replace – and they also *need* to be replaced often, as there is always the danger of leaking the server certificate. If a certificate is going to expire in two weeks anyway, an attacker is less likely to steal it.
- With intermediate CA certificates, one might hope that the situation is clear: Servers can't expect that they are already stored on the client, so they *should* be sent while establishing a connection. Logic (and the specification, [e.g. RFC 5246 7.4.2](https://www.rfc-editor.org/rfc/rfc5246)) requires that the full chain be sent, or else it cannot possibly be validated.

## The problem

Well, intermediate CA certificates are long-lived, and used for many many websites. So long lived, and for so many websites, that sending the same certificate over and over and over again seems a bit redundant. So some servers just plain and simple do not send them. This is incorrect behavior, and should be regarded as an error.

This has been [done in the past](https://www.ssltools.com/report/f3dbb1c6-1c02-40eb-9069-3796f002e7cd), and is being [done in the present](https://www.ssllabs.com/ssltest/analyze.html?d=eatcs.org) by many servers. Too many to list them here.

But of course we don't want to show an error to the user. So [some browsers](https://security.stackexchange.com/a/211750) keep a store of intermediate CA certificates, which kinda mostly works if this intermediate store is well-maintained (which requires a constant search for missed intermediates; note that I trust that Mozilla keeps up this particular project), and users regularly apply updates (because intermediate CA certificates very much expire) or have auto-updates (Firefox seems to auto-fetch the intermediate-ca store on startup), and you don't visit any websites whose certification path is too new (and use intermediate CA certificates you haven't seen yet).

So now we have this awful situation, where everything kinda mostly works apparently, but is completely unusable to automated tools.
It is unreasonable to demand that thousands of sysadmins out there go and change their webserver's setup, so a different solution is necessary.

## The solution in this project

… is just as terrible as all other solutions, but it's better than nothing. The approach taken by my code is:
- Download (if not already cached) the current store [via the current ccadb store](https://firefox.settings.services.mozilla.com/v1/buckets/security-state/collections/intermediates/records)
- Create a CAINFO bundle of PEM certificates by concatenating the results
- Use that with curl/requests/whatever you want

To save resources and avoid hammering the Mozilla servers with thousands of requests, I created an easily-downloadable bundle at [https://raw.githubusercontent.com/BenWiederhake/intermediate-ca-bundle/blob/intermediate_certs.pem](https://raw.githubusercontent.com/BenWiederhake/intermediate-ca-bundle/blob/intermediate_certs.pem). Please be nice to GitHub and don't hammer that URL either. I promise the file won't change that often, simply to save my own resources.

Note that by construction, this bundle will become outdated rather quickly, so you should rebuild/refetch it about every week or so.

## See also

- https://www.ccadb.org/resources
- https://donate.mozilla.org/
- https://wiki.mozilla.org/Security/CryptoEngineering/Intermediate_Preloading
- https://searchfox.org/mozilla-central/source/services/settings/Attachments.sys.mjs#374
- https://remote-settings.readthedocs.io/en/latest/tutorial-attachments.html#publish-records-with-attachments
- https://github.com/mozilla/remote-settings/blob/1cfb199a8648abdc89f79dea7c9f8e5f27902c7a/docs/getting-started.rst#L73
- E-Mail uses a different set of intermediate certs: https://thunderbird-settings.thunderbird.net/v1/

## Installation

You really shouldn't install this anywhere.

## Usage

You most definitely don't need to run this code:
- If you just need a bundle, my cronjob should rebuild it every week, and you can [download it here](https://raw.githubusercontent.com/BenWiederhake/intermediate-ca-bundle/blob/intermediate_certs.pem).
- If you need a highly-accurate, up-to-date cert store, then you should be running an actual kinto client and stay synchronized that way.

But let's ignore that for now, and assume you have a good reason to run the code anyway. (If it's because the bundle is no longer updating, something has gone very wrong. Help, I guess?)

Usage is dead-simple:
- `pip install -r requirements.txt  # or just 'pip install requests'`
- `mkdir -p intermediate_certs`
- `cp secret_config_template.py secret_config.py`
- `nano secret_config.py  # Write your real e-mail address, in case your crawler causes an emergency`
- `./fetch_all.py`

That's it.

The output will be in `intermediate_certs/intermediate_certs.pem` alongside the individual (possibly outdated) certificates and records list.

Note that this is only so easy because Mozilla (and not me) is doing all the hard work of vetting root CAs, collecting intermediate CA certificates, and running the servers. Consider [donating to them](https://donate.mozilla.org/).

## Formats, and ease of access

Finally, let me observe something silly:
```
$ du -h records.json intermediate_certs.pem.gz intermediate_certs.pem.xz
1,3M	records.json
1,3M	intermediate_certs.pem.gz
1,1M	intermediate_certs.pem.xz
```

So using the kinto system has huge CPU and network overhead for client and server, since it requires between a handful up to a thousand of individual requests; one request for each of the 1400 certs.

On the other hand, just making the bundle directly available for download would be *smaller* than just the first request in your fancy diffable system!

I believe projects like this should never be necessary. You have the data, you want to share the data with the world, and you chose a format that makes it harder to access the data. Why?!

(Please note that my only gripe is this choice of format. I still think [Mozilla](https://donate.mozilla.org/) is awesome! I actually enjoyed the discoverability of the kinto API!)

## TODOs

* Use it for the thing I'm working on
* Automate weekly uploads to GitHub pages
* Let it run for a while
* Show it to other people

## NOTDOs

Here are some things this project will probably not support:
* Most config-style stuff. Keep the script simple.
* Actually calling kinto. Reading up on it took longer than just writing those 65 SLOC of python myself.
* Any kind of low-latency service. Mozilla's kinto store is already perfect for that, and the CA bundle would be unwieldy.
* Any kind of verification or cross-checking. This is an automated process, and I want something that works better than what I had before. If you want high-security connections, you should instead ask your webadmin why the hell his certificate chain is incomplete.

## License

I referenced Mozilla's code and documentation a lot while writing this, so I feel obliged to make this project available under the identical [Apache License](./LICENSE). Please [contact me](https://github.com/BenWiederhake/intermediate-ca-bundle/issues/new) if that somehow is an issue for you.

## Contribute

Feel free to dive in! [Open an issue](https://github.com/BenWiederhake/intermediate-ca-bundle/issues/new) or submit PRs.
