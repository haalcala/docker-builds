package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/hashicorp/memberlist"
)

type eventDelegate struct {
	nodes    []string
	items    *map[string]int64
	delegate *delegate
}

type broadcast struct {
	msg    []byte
	notify chan<- struct{}
}

type delegate struct {
	mtx        *sync.RWMutex
	items      *map[string]int64
	broadcasts *memberlist.TransmitLimitedQueue
	cluster    *SimpleCluster
}

type update struct {
	Action string // add, del
	Data   *map[string]string
	Msg    *ClusterMessage
}

type members_data struct {
	Timestamp int64
	Members   map[string]int64
	Remarks   string
}

func main() {
	var bind_address string
	var initial_seed string
	var bind_port int

	flag.StringVar(&bind_address, "b", "", "Default bind_address: root")
	flag.StringVar(&initial_seed, "s", "", "Default initial_seed: mysql")

	flag.Parse()

	fmt.Println("bind_address:", bind_address)
	fmt.Println("initial_seed:", initial_seed)

	if bind_address == "" || initial_seed == "" {
		fmt.Println(errors.New("bind_address (-b) and initial_seed (-s) are required"))

		return
	}

	_bind_address := strings.Split(bind_address, ":")

	start_time := time.Now().Unix()

	s := &SimpleCluster{
		items:       map[string]int64{},
		start_time:  start_time,
		initialised: false,
		isReady:     false,
		stopping:    false,
		stopped:     false,
	}

	fmt.Println("pid:", os.Getpid())

	hostname, err := os.Hostname()

	if err != nil {
		panic(err)
	}

	clusterInfo := &ClusterInfo{
		Hostname: hostname,
		Id:       fmt.Sprintf("%v-%v", hostname, os.Getpid()),
		// IPAddress: ip.String(),
	}

	s.clusterInfo = clusterInfo

	if len(_bind_address) > 1 {
		bind_port, err = strconv.Atoi(_bind_address[1])

		if err != nil {
			panic(err)
		}
	}

	eventDelegate, m, err := s.startWithPort(clusterInfo.Id, bind_port)

	if err != nil {
		panic(err)
	}

	s.memberlist = m
	s.eventDelegate = eventDelegate

	this_node := m.LocalNode()
	s.this_node = this_node

	s.items[this_node.Address()] = s.start_time

	clusterInfo.IPAddress = this_node.Address()

	m.Join([]string{initial_seed})

	if bind_address == ":2222" {
		go func() {
			time.Sleep(10 * time.Second)
			var loop_count int

			batch_size := 1000

			for {
				for i := range make([]byte, batch_size) {
					msg := &ClusterMessage{
						Event: fmt.Sprintf("custom_event_%v", (loop_count*batch_size)+i),
						Data:  []byte(fmt.Sprintf("{\"msg_id\":%v}", i)),
					}

					s.SendClusterMessage(msg)
				}

				loop_count += 1

				time.Sleep(10 * time.Second)
			}
		}()
	}

	// Create a channel to listen for exit signals
	stop := make(chan os.Signal, 1)

	// Register the signals we want to be notified, these 3 indicate exit
	// signals, similar to CTRL+C
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)

	<-stop

	fmt.Println("Stopping!!!!")

	// Leave the cluster with a 5 second timeout. If leaving takes more than 5
	// seconds we return.
	if err := m.Leave(time.Second * 5); err != nil {
		panic(err)
	}

	m.Shutdown()
}
