iftest:
	rm -rf .pids/*
	python ./src/egt.py tests/iftest.py > if.py
	python if.py
	for i in .pids/*; do echo $$i `cat $$i`; done
