package main

import "testing"

func TestParseLsofLinesTCP(t *testing.T) {
	out := []byte(`COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
rapportd    976 rdubar   10u  IPv4 0xe8cc5ee43b776a96      0t0  TCP *:53977 (LISTEN)
rapportd    976 rdubar   11u  IPv6 0x3ce970eb7bc961be      0t0  TCP *:53977 (LISTEN)
TextMate   1488 rdubar    7u  IPv6 0xcc905849e2e86b34      0t0  TCP [::1]:52698 (LISTEN)
`)
	entries := parseLsofLines(out, "tcp")
	if len(entries) != 2 {
		t.Fatalf("expected 2 entries after IPv4/IPv6 dedupe, got %d: %+v", len(entries), entries)
	}
	if entries[0].Port != 53977 || entries[0].Process != "rapportd" || entries[0].PID != 976 {
		t.Errorf("unexpected first entry: %+v", entries[0])
	}
	if entries[1].Port != 52698 {
		t.Errorf("expected second entry port 52698, got %+v", entries[1])
	}
}

func TestParseLsofLinesUDPWildcardSkipped(t *testing.T) {
	out := []byte(`COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
identitys  1000 rdubar   11u  IPv4 0x2cf531f7525284c2      0t0  UDP *:*
rapportd    976 rdubar   23u  IPv4 0xed040c1e99763b3f      0t0  UDP *:3722
`)
	entries := parseLsofLines(out, "udp")
	if len(entries) != 1 || entries[0].Port != 3722 {
		t.Fatalf("expected only the fixed-port UDP entry, got %+v", entries)
	}
}

func TestParseSSLines(t *testing.T) {
	out := []byte(`State   Recv-Q  Send-Q   Local Address:Port   Peer Address:Port  Process
LISTEN  0       128            0.0.0.0:22          0.0.0.0:*      users:(("sshd",pid=1234,fd=3))
LISTEN  0       128               [::]:80             [::]:*      users:(("nginx",pid=99,fd=6))
`)
	entries := parseSSLines(out, "tcp")
	if len(entries) != 2 {
		t.Fatalf("expected 2 entries, got %d: %+v", len(entries), entries)
	}
	if entries[0].Port != 22 || entries[0].Process != "sshd" || entries[0].PID != 1234 {
		t.Errorf("unexpected first entry: %+v", entries[0])
	}
	if entries[1].Port != 80 || entries[1].Process != "nginx" {
		t.Errorf("unexpected second entry: %+v", entries[1])
	}
}

func TestParseBrewList(t *testing.T) {
	out := []byte("jq 1.8.1\nzstd 1.5.7\n")
	pkgs := parseBrewList(out)
	if pkgs["jq"] != "1.8.1" || pkgs["zstd"] != "1.5.7" {
		t.Fatalf("unexpected parse result: %+v", pkgs)
	}
}

func TestParseDpkgList(t *testing.T) {
	out := []byte("bash\t5.1-6\ncoreutils\t8.32-4\n")
	pkgs := parseDpkgList(out)
	if pkgs["bash"] != "5.1-6" || pkgs["coreutils"] != "8.32-4" {
		t.Fatalf("unexpected parse result: %+v", pkgs)
	}
}
