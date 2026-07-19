package main

import "testing"

func TestFirstRunPayloadIsWellShaped(t *testing.T) {
	payload := firstRunPayload()
	if payload["first_run"] != true {
		t.Errorf("expected first_run=true, got %+v", payload["first_run"])
	}
	if payload["change_count"] != 0 || payload["notable_count"] != 0 {
		t.Errorf("expected zero counts on a first run, got %+v", payload)
	}
	changes, ok := payload["changes"].([]any)
	if !ok || len(changes) != 0 {
		t.Errorf("expected an empty changes array, got %+v", payload["changes"])
	}
}
