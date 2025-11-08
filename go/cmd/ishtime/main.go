package main

import (
	"errors"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"strconv"
	"strings"
	"time"
)

func usage() {
	fmt.Fprintf(os.Stderr, `Usage: ishtime [options]

Describe the current time (or a supplied time) in conversational "ish" form.

Options:
`)
	flag.PrintDefaults()
}

func main() {
	flag.Usage = usage

	timeFlag := flag.String("time", "", "Describe the provided time (e.g. 11:20, 1320, 07:44:30)")
	randomFlag := flag.Bool("random", false, "Generate a random ish time")
	flag.Parse()

	var hour, minute, second int
	var err error
	useFallback := true

	switch {
	case *randomFlag:
		rand.Seed(time.Now().UnixNano())
		hour = rand.Intn(24)
		minute = rand.Intn(60)
		second = rand.Intn(60)
		useFallback = false
	case strings.TrimSpace(*timeFlag) != "":
		hour, minute, second, err = parseInputTime(*timeFlag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			os.Exit(1)
		}
		useFallback = false
	default:
		now := time.Now()
		hour, minute, second = now.Hour(), now.Minute(), now.Second()
	}

	fmt.Println(describeIsh(hour, minute, second, useFallback))
}

func parseInputTime(input string) (int, int, int, error) {
	input = strings.TrimSpace(input)
	if input == "" {
		return 0, 0, 0, errors.New("empty time value")
	}

	if strings.Contains(input, ":") {
		parts := strings.Split(input, ":")
		if len(parts) < 2 || len(parts) > 3 {
			return 0, 0, 0, fmt.Errorf("invalid time format: %q", input)
		}
		values := make([]int, 3)
		for i := range values {
			if i < len(parts) {
				v, err := strconv.Atoi(parts[i])
				if err != nil {
					return 0, 0, 0, fmt.Errorf("invalid time component %q", parts[i])
				}
				values[i] = v
			}
		}
		return values[0], values[1], values[2], nil
	}

	digits := input
	if len(digits) < 2 {
		return 0, 0, 0, fmt.Errorf("invalid time format: %q", input)
	}
	for len(digits) < 4 {
		digits += "0"
	}

	hour, err := strconv.Atoi(digits[:2])
	if err != nil {
		return 0, 0, 0, fmt.Errorf("invalid hour component %q", digits[:2])
	}

	minute, err := strconv.Atoi(digits[2:4])
	if err != nil {
		return 0, 0, 0, fmt.Errorf("invalid minute component %q", digits[2:4])
	}

	second := 0
	if len(digits) > 4 {
		secDigits := digits[4:]
		if len(secDigits) > 2 {
			secDigits = secDigits[:2]
		}
		second, err = strconv.Atoi(secDigits)
		if err != nil {
			return 0, 0, 0, fmt.Errorf("invalid second component %q", secDigits)
		}
	}

	return hour, minute, second, nil
}

func describeIsh(hour, minute, second int, fallback bool) string {
	if fallback && hour == 0 && minute == 0 && second == 0 {
		now := time.Now()
		hour, minute, second = now.Hour(), now.Minute(), now.Second()
	}

	period := daytime(hour)

	adjustedHour := hour
	adjustedMinute := minute

	if adjustedMinute > 57 && second > 30 {
		adjustedMinute++
	}
	if adjustedMinute > 60 {
		adjustedMinute = 0
	}
	if adjustedMinute > 33 {
		adjustedHour++
	}

	clockHour := adjustedHour % 12
	if clockHour == 0 {
		clockHour = 12
	}

	if adjustedMinute <= 3 || adjustedMinute > 57 {
		return fmt.Sprintf("It is about %s o'clock %s.", numberWord(clockHour), period)
	}

	if adjustedMinute <= 33 && adjustedMinute > 28 {
		return fmt.Sprintf("It is about half past %s %s.", numberWord(clockHour), period)
	}

	connector := "past"
	if adjustedMinute >= 30 {
		connector = "to"
	}

	return fmt.Sprintf("It is about %s %s %s %s.", bitTime(adjustedMinute), connector, numberWord(clockHour), period)
}

func numberWord(x int) string {
	words := []string{"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"}
	if x >= 1 && x <= len(words) {
		return words[x-1]
	}
	return strconv.Itoa(x)
}

func bitTime(m int) string {
	switch {
	case m <= 7 || m > 53:
		return "five minutes"
	case m <= 12 || m > 48:
		return "ten minutes"
	case m <= 17 || m > 43:
		return "quarter"
	case m <= 23 || m > 38:
		return "twenty minutes"
	case m <= 28 || m > 33:
		return "twenty-five minutes"
	default:
		return "five minutes"
	}
}

func daytime(hour int) string {
	switch {
	case hour == 0 || hour > 21:
		return "at night"
	case hour < 12:
		return "in the morning"
	case hour <= 17:
		return "in the afternoon"
	default:
		return "in the evening"
	}
}
