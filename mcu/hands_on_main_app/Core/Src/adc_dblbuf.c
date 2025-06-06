#include <stdbool.h>
#include <stdint.h>
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

#define ALPHA 0.0f               // facteur de lissage pour le seuil
#define ENERGY_MULTIPLIER 0.0f    // facteur multiplicatif du seuil

static int remaining_vectors_to_compute = 0;
static float avg_energy = 0.0f;

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
// Seuil de tension brut ADC (à ajuster selon ta résolution et tension de référence)
uint32_t seuil = 40;

// Fonction pour lire la tension du condensateur via l'ADC
uint32_t Read_capacitor_voltage()
{
    HAL_ADC_Start(&hadc2);
    HAL_ADC_PollForConversion(&hadc2, HAL_MAX_DELAY);

    uint32_t value = HAL_ADC_GetValue(&hadc2);
    HAL_ADC_Stop(&hadc2);

    return value;
}

// Fonction pour vérifier si l'énergie est suffisante
bool HasEnoughEnergy()
{
    uint32_t value = Read_capacitor_voltage();
    return value >= seuil;
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

bool sound_bigger_than_adaptive_threshold(q15_t *buf) {
    int64_t energy = 0;
    const int32_t adc_zero = 2048; // Vdd/2 pour un ADC 12 bits

    int i = 0;
    while (i < ADC_BUF_SIZE) {
        // Traitement par paquet de 4 échantillons pour réduire les dépendances et améliorer le pipeline CPU
        int32_t s0 = (int32_t)buf[i++] - adc_zero;
        int32_t s1 = (int32_t)buf[i++] - adc_zero;
        int32_t s2 = (int32_t)buf[i++] - adc_zero;
        int32_t s3 = (int32_t)buf[i++] - adc_zero;

        energy += (int64_t)s0 * s0 + (int64_t)s1 * s1 + (int64_t)s2 * s2 + (int64_t)s3 * s3;
    }

    // Mise à jour de l'énergie moyenne avec un facteur ALPHA
    avg_energy = ALPHA * avg_energy + (1.0f - ALPHA) * (float)energy;
    float threshold = ENERGY_MULTIPLIER * avg_energy;

    return (energy > threshold);
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
    } else if (ADCDataRdy[1 - buf_cplt]) {
        DEBUG_PRINT("Error: ADC Data buffer full\r\n");
        Error_Handler();
    }

    ADCDataRdy[buf_cplt] = 1;

    // ---- Ajout logique seuil + compteur ----
    bool process_buffer = false;

    if (remaining_vectors_to_compute > 0) {
            process_buffer = true;
            remaining_vectors_to_compute--;
    } else if (HasEnoughEnergy()) {
        if(sound_bigger_than_adaptive_threshold((q15_t *)ADCData[buf_cplt])){
            process_buffer = true;
            remaining_vectors_to_compute = N_MELVECS - 1;  // On a déjà 1 melvec ici, on en veut 19 de plus
        }
    }

    if (process_buffer) {
        Spectrogram_Format((q15_t *)ADCData[buf_cplt]);
        Spectrogram_Compute((q15_t *)ADCData[buf_cplt], mel_vectors[cur_melvec]);
        cur_melvec++;
    } else {
        DEBUG_PRINT("Énergie trop faible : buffer ignoré.\r\n");
    }

    ADCDataRdy[buf_cplt] = 0;

    if (rem_n_bufs == 0 && cur_melvec == N_MELVECS) {
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
