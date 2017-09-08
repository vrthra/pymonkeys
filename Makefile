%:
	rm -rf .pids/*
	python ./src/symexec.py tests/$*.py > x.py
	python x.py
	for i in .pids/*; do echo $$i `cat $$i`; done

clean:
	rm -rf .pids/
	mkdir -p .pids

pudb-%:
	python -mpudb ./src/symexec.py tests/$*.py
ipdb-%:
	python -mipdb ./src/symexec.py tests/$*.py
