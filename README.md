Using r2 cli
==

**Show all nodes:**

    r2 node show

**Show details about a particular node:**

    r2 node show <node id>

**Show all adventures:**

    r2 adventure show

**Show details about a particular adventure:**

    r2 adventure show <adventure id>

**Show adventures a node can execute:**

    r2 node show <node id> adventures

**Execute an adventure on a particular node:**

    r2 adventure execute <adventure id> --node=<node id>

**Show all tasks:**

    r2 task show

**Show details about a particular task:**

    r2 task show <task id>

**Specify roush server endpoint:**

    ROUSH_ENDPOINT=http://<roush server>:8080 r2 node show

or:

    r2 node show --endpoint=http://<roush server>:8080

Using roushcli
==

**Show all nodes:**

    roushcli node list

**Show details about a particular node:**

    roushcli node show --id=<node id>

**Show all adventures:**

    roushcli adventure list

**Show details about a particular adventure:**

    roushcli adventure show --id=<adventure id>

**Show adventures a node can execute:**

    TBD

**Execute an adventure on a particular node:**

    TBD

**Show all tasks:**

    roushcli task list

**Show details about a particular task:**

    roushcli task show --id=<task id>

**Specify roush server endpoint:**

    ROUSH_ENDPOINT=http://<roush server>:8080 roushcli node list
