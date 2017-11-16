MAKEFLAGS += --no-builtin-rules
.SUFFIXES:

.PRECIOUS: .symbolic/%.py

%.sym: .symbolic/%.py | .symbolic .pids
	rm -rf .pids/*
	python3 .symbolic/$*.py
	for i in .pids/*; do echo $$i `cat $$i`; done


.symbolic/%.py: tests/%.py | .symbolic
	python3 ./src/symexec.py tests/$*.py > .symbolic/$*.py

clean:
	rm -rf .pids/ .symbolic

.symbolic:; mkdir -p .symbolic
.pids:; mkdir -p .pids

pudb-%:
	python3 -mpudb ./src/symexec.py tests/$*.py
ipdb-%:
	python3 -mipdb ./src/symexec.py tests/$*.py
