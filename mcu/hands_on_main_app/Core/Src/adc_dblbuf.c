#include <adc_dblbuf.h>
#include "config.h"
#include "main.h"
#include "spectrogram.h"
#include "arm_math.h"
#include "utils.h"
#include "s2lp.h"
#include "packet.h"


static volatile uint16_t ADCDoubleBuf[2*ADC_BUF_SIZE]; /* ADC group regular conversion data (array of data) */
static volatile uint16_t* ADCData[2] = {&ADCDoubleBuf[0], &ADCDoubleBuf[ADC_BUF_SIZE]};
static volatile uint8_t ADCDataRdy[2] = {0, 0};

static volatile uint8_t cur_melvec = 0;
static q15_t mel_vectors[N_MELVECS][MELVEC_LENGTH];

static uint32_t packet_cnt = 0;

static volatile int32_t rem_n_bufs = 0;

int StartADCAcq(int32_t n_bufs) {
	rem_n_bufs = n_bufs;
	cur_melvec = 0;
	if (rem_n_bufs != 0) {
		return HAL_ADC_Start_DMA(&hadc1, (uint32_t *)ADCDoubleBuf, 2*ADC_BUF_SIZE);
	} else {
		return HAL_OK;
	}
}

int IsADCFinished(void) {
	return (rem_n_bufs == 0);
}

static void StopADCAcq() {
	HAL_ADC_Stop_DMA(&hadc1);
}

static void print_spectrogram(void) {
#if (DEBUGP == 1)
	start_cycle_count();
	DEBUG_PRINT("Acquisition complete, sending the following FVs\r\n");
	for(unsigned int j=0; j < N_MELVECS; j++) {
		DEBUG_PRINT("FV #%u:\t", j+1);
		for(unsigned int i=0; i < MELVEC_LENGTH; i++) {
			DEBUG_PRINT("%.2f, ", q15_to_float(mel_vectors[j][i]));
		}
		DEBUG_PRINT("\r\n");
	}
	stop_cycle_count("Print FV");
#endif
}

static void print_encoded_packet(uint8_t *packet) {
#if (DEBUGP == 1)
	char hex_encoded_packet[2*PACKET_LENGTH+1];
	hex_encode(hex_encoded_packet, packet, PACKET_LENGTH);
	DEBUG_PRINT("DF:HEX:%s\r\n", hex_encoded_packet);
#endif
}

static void encode_packet(uint8_t *packet, uint32_t* packet_cnt) {
    // Étape 1 : Trouver la valeur max absolue dans l’ensemble du Mel-Vecteur
    q15_t vmax = 0;

    for (size_t i = 0; i < N_MELVECS; i++) {
        for (size_t j = 0; j < MELVEC_LENGTH; j++) {
            q15_t abs_val = (mel_vectors[i][j] < 0) ? -mel_vectors[i][j] : mel_vectors[i][j];
            if (abs_val > vmax) {
                vmax = abs_val;
            }
        }
    }

    // Étape 2 : Calcul du shift optimal pour rester dans Q7 [-128, 127]
    uint8_t shift = 0;
    while (vmax > 127 && shift < 8) {
        vmax >>= 1;
        shift++;
    }

    // Étape 3 : Appliquer le shift et encoder les données en Q7
    for (size_t i = 0; i < N_MELVECS; i++) {
        for (size_t j = 0; j < MELVEC_LENGTH; j++) {
            q15_t scaled_value = mel_vectors[i][j] >> shift;

            // Saturation sur 8 bits signés
            if (scaled_value > 127) scaled_value = 127;
            if (scaled_value < -128) scaled_value = -128;

            // Stockage dans le packet (en tant que uint8_t)
            (packet + PACKET_HEADER_LENGTH)[i * MELVEC_LENGTH + j] = (uint8_t)(scaled_value & 0xFF);
        }
    }

    // Étape 4 : Création du paquet avec shift dans l'en-tête (champ réservé)
    make_packet(packet, PAYLOAD_LENGTH, shift, 0, *packet_cnt); // shift envoyé ici

    *packet_cnt += 1;

    // Protection contre l'overflow (théorique)
    if (*packet_cnt == 0) {
        DEBUG_PRINT("Packet counter overflow.\r\n");
        Error_Handler();
    }
}

static void send_spectrogram() {
	uint8_t packet[PACKET_LENGTH];

	start_cycle_count();
	encode_packet(packet, &packet_cnt);
	stop_cycle_count("Encode packet");

	start_cycle_count();
	S2LP_Send(packet, PACKET_LENGTH);
	stop_cycle_count("Send packet");

	print_encoded_packet(packet);
}

static void ADC_Callback(int buf_cplt) {
	if (rem_n_bufs != -1) {
		rem_n_bufs--;
	}
	if (rem_n_bufs == 0) {
		StopADCAcq();
	} else if (ADCDataRdy[1-buf_cplt]) {
		DEBUG_PRINT("Error: ADC Data buffer full\r\n");
		Error_Handler();
	}
	ADCDataRdy[buf_cplt] = 1;
	//start_cycle_count();
	Spectrogram_Format((q15_t *)ADCData[buf_cplt]);
	Spectrogram_Compute((q15_t *)ADCData[buf_cplt], mel_vectors[cur_melvec]);
	cur_melvec++;
	//stop_cycle_count("spectrogram");
	ADCDataRdy[buf_cplt] = 0;

	if (rem_n_bufs == 0) {
		print_spectrogram();
		send_spectrogram();
	}
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
	ADC_Callback(1);
}

void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc)
{
	ADC_Callback(0);
}
