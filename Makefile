iftest:
	rm -rf .pids/*
	python ./src/egtexec.py tests/iftest.py > if.py
	python if.py
	for i in .pids/*; do echo $$i `cat $$i`; done

clean:
	rm -rf .pids/
	mkdir -p .pids
